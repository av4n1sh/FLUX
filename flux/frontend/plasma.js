/* Shared internal-energy renderer. One small surface serves every visible Flux orb. */
'use strict';
window.FluxPlasma = (() => {
  const vertex = `attribute vec2 position;
    varying vec2 uv;
    void main(){uv=position*.5+.5;gl_Position=vec4(position,0.,1.);}`;
  const fragment = `precision mediump float;
    varying vec2 uv;
    uniform sampler2D reference;
    uniform float time, energy, audio, swirl, pulse, gentle, aspect;
    float hash(vec3 p){p=fract(p*.3183099+vec3(.13,.27,.37));p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
    float noise(vec3 p){
      vec3 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
      return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
                 mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
    }
    void main(){
      vec2 p=(uv-.5)*2.;
      float a=atan(p.y,p.x), t=time, strength=mix(1.,.3,gentle);
      float morph=strength*(.016*sin(5.*a-t*.73)+.011*sin(7.*a+t*1.13)+.007*sin(3.*a+t*.39));
      float boundary=.735*(1.+morph+audio*.012*sin(4.*a-t));
      vec2 q=p/boundary; float r=length(q);
      float z=sqrt(max(0.,1.-r*r));
      // Domain-warped 3D coordinates give the near surface and the deeper energy different motion.
      float twist=(.09+swirl*.17)*sin(t*.31+r*4.2)*strength;
      mat2 rotation=mat2(cos(twist),-sin(twist),sin(twist),cos(twist));
      vec3 sphere=vec3(rotation*q,z);
      vec3 drift=vec3(t*.13,-t*.19,t*.095);
      float cloud=noise(sphere*3.1+drift);
      float depth=noise(sphere*5.7+vec3(cloud*1.7,t*.17,-t*.11));
      float current=noise(sphere*8.3+vec3(depth*1.4,-t*.25,cloud));
      float band=sin(cloud*13.+depth*5.+a*1.3-r*5.-t*(.6+swirl));
      float vein=pow(max(0.,1.-abs(band)),6.);
      float wave=pow(.5+.5*sin(r*16.-t*2.1+depth*4.),5.)*pulse;
      vec2 displacement=vec2(cloud-.5,depth-.5)*(.085+energy*.065)*strength;
      vec2 tex=(rotation*q+displacement)*.5+.5;
      tex=clamp(tex,vec2(.002),vec2(.998));
      vec3 original=texture2D(reference,vec2(tex.x,(1.-tex.y)*aspect+(1.-aspect)*.5)).rgb;
      float facing=.45+.55*z;
      vec3 plasma=mix(vec3(.24,.018,.36),vec3(.91,.20,.68),smoothstep(.22,.80,cloud));
      plasma+=vec3(.69,.28,.75)*depth*.40;
      vec3 c=original*(.57+cloud*.18)+plasma*(.29+energy*.14)*facing;
      c+=vec3(1.,.53,.91)*vein*(.16+energy*.22)*facing;
      c+=vec3(.80,.26,.67)*wave*.17*(1.-smoothstep(.8,1.,r));
      // A moving local highlight and a softer rear light create volume, not a flat gradient disc.
      vec2 highlight=vec2(-.24+sin(t*.37)*.17,.24+cos(t*.29)*.13);
      float hotspot=exp(-dot(q-highlight,q-highlight)*10.)*(.19+current*.13);
      c+=vec3(1.,.82,.96)*hotspot;
      float rim=exp(-pow((r-.87)*16.,2.))*(.08+cloud*.15+vein*.08);
      c+=vec3(.92,.08,.62)*rim;
      c*=.73+.27*z;
      float body=1.-smoothstep(.935,1.025,r);
      float halo=exp(-max(0.,r-.80)*7.)*.17*(.8+energy*.4);
      float alpha=max(body,halo);
      vec3 color=mix(vec3(.62,.035,.46),c,body);
      alpha*=1.-smoothstep(1.25,1.43,r);
      gl_FragColor=vec4(color*alpha,alpha);
    }`;

  class Renderer {
    constructor(){
      this.surface=document.createElement('canvas');this.surface.width=this.surface.height=320;
      this.frames=0;this.cost=0;this.kind='loading';this.ready=false;
      this.image=new Image();
      this.image.onload=()=>{
        this.aspect=this.image.naturalWidth/this.image.naturalHeight;
        this.prepareSource();
        if(!this.initGL())this.useFallback();
        this.ready=true;
      };
      this.image.onerror=()=>{this.ready=true;this.useFallback();};
      this.image.src='../assets/flux-orb.png';
    }
    prepareSource(){
      const c=document.createElement('canvas');c.width=c.height=160;
      const ctx=c.getContext('2d',{willReadFrequently:true});
      const side=this.image.naturalWidth;
      ctx.drawImage(this.image,0,(this.image.naturalHeight-side)/2,side,side,0,0,160,160);
      this.source=ctx.getImageData(0,0,160,160).data;
    }
    initGL(){
      try{
        const gl=this.surface.getContext('webgl',{alpha:true,antialias:false,depth:false,stencil:false,premultipliedAlpha:true,preserveDrawingBuffer:true,powerPreference:'low-power'});
        if(!gl)return false;
        this.gl=gl;
        const compile=(type,code)=>{const shader=gl.createShader(type);gl.shaderSource(shader,code);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(shader));return shader;};
        const vs=compile(gl.VERTEX_SHADER,vertex),fs=compile(gl.FRAGMENT_SHADER,fragment);
        const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
        if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
        gl.deleteShader(vs);gl.deleteShader(fs);gl.useProgram(program);
        const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
        gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
        const attr=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(attr);gl.vertexAttribPointer(attr,2,gl.FLOAT,false,0,0);
        const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
        gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,this.image);
        this.uniforms={};for(const name of ['time','energy','audio','swirl','pulse','gentle','aspect'])this.uniforms[name]=gl.getUniformLocation(program,name);
        gl.viewport(0,0,320,320);this.kind='webgl';
        this.surface.addEventListener('webglcontextlost',event=>{event.preventDefault();this.useFallback();},{once:true});
        return true;
      }catch(error){console.warn('Flux orb: using Canvas renderer.',error.message);return false;}
    }
    useFallback(){
      if(this.kind==='canvas')return;
      this.surface=document.createElement('canvas');this.surface.width=this.surface.height=160;
      this.ctx=this.surface.getContext('2d');this.pixels=this.ctx.createImageData(160,160);
      this.geometry=new Float32Array(160*160*4);
      for(let y=0;y<160;y++)for(let x=0;x<160;x++){
        const i=(y*160+x)*4,px=(x+.5)/80-1,py=1-(y+.5)/80;
        this.geometry[i]=px;this.geometry[i+1]=py;this.geometry[i+2]=Math.hypot(px,py);this.geometry[i+3]=Math.atan2(py,px);
      }
      this.kind='canvas';
    }
    render(t,params,audio,gentle){
      if(!this.ready)return false;
      const began=performance.now();
      if(this.kind==='webgl'){
        const values={time:t,energy:params.energy,audio,swirl:params.swirl,pulse:params.pulse,gentle:gentle?1:0,aspect:this.aspect};
        for(const [key,value] of Object.entries(values))this.gl.uniform1f(this.uniforms[key],value);
        this.gl.drawArrays(this.gl.TRIANGLES,0,6);
      }else this.renderCanvas(t,params,audio,gentle);
      this.frames++;this.cost=this.cost*.9+(performance.now()-began)*.1;
      return true;
    }
    renderCanvas(t,p,audio,gentle){
      const data=this.pixels.data,g=this.geometry,source=this.source,strength=gentle?.3:1;
      const clamp=v=>Math.min(255,Math.max(0,v));
      // Spatially varying warp and illumination: this fallback also changes internal pixels,
      // rather than translating or rotating a reference image as one piece.
      for(let i=0;i<data.length;i+=4){
        const angle=g[i+3],boundary=.735*(1+strength*(.016*Math.sin(5*angle-t*.73)+.011*Math.sin(7*angle+t*1.13)+.007*Math.sin(3*angle+t*.39)));
        const r=g[i+2]/boundary;
        if(r>1.4){data[i+3]=0;continue;}
        const x=g[i]/boundary,y=g[i+1]/boundary,z=Math.sqrt(Math.max(0,1-r*r));
        const cloud=.5+.25*Math.sin(x*5+y*3+t*.53+Math.sin(y*6-t*.41))+.25*Math.sin(y*5-x*2-t*.39+z*4);
        const depth=.5+.5*Math.sin(x*8-y*6+t*.71+cloud*4+z*3);
        const bend=(.025+p.swirl*.02)*strength;
        const wx=x+Math.sin(y*7+t*.61+cloud*3)*bend,wy=y+Math.sin(x*6-t*.53+depth*2)*bend;
        const tx=Math.min(159,Math.max(0,Math.round((wx*.5+.5)*159))),ty=Math.min(159,Math.max(0,Math.round((.5-wy*.5)*159)));
        const si=(ty*160+tx)*4;
        const vein=Math.pow(Math.max(0,1-Math.abs(Math.sin(cloud*13+depth*5+angle*1.3-r*5-t*(.6+p.swirl)))),6);
        const wave=Math.pow(.5+.5*Math.sin(r*16-t*2.1+depth*4),5)*p.pulse;
        const light=(vein*(.12+p.energy*.17)+wave*.08+audio*.09)*(.45+.55*z);
        const base=.58+cloud*.18,shade=.73+.27*z;
        const body=Math.min(1,Math.max(0,(1.025-r)/.09));
        const alpha=Math.max(body,Math.exp(-Math.max(0,r-.8)*7)*.17)*Math.min(1,Math.max(0,(1.4-r)/.2));
        const red=((source?source[si]:180)*base+cloud*35+light*255)*shade;
        const green=((source?source[si+1]:55)*base+depth*12+light*135)*shade;
        const blue=((source?source[si+2]:160)*base+cloud*32+light*233)*shade;
        data[i]=clamp(red*body+158*(1-body));data[i+1]=clamp(green*body+9*(1-body));data[i+2]=clamp(blue*body+117*(1-body));data[i+3]=alpha*255;
      }
      this.ctx.putImageData(this.pixels,0,0);
    }
    get diagnostics(){return {renderer:this.kind,frames:this.frames,resolution:this.surface.width,averageRenderMs:Math.round(this.cost*100)/100};}
  }
  return new Renderer();
})();
