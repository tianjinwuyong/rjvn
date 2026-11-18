import * as THREE from "../../../smt-factory-system/node_modules/three/build/three.module.js";
import { GLTFExporter } from "../../../smt-factory-system/node_modules/three/examples/jsm/exporters/GLTFExporter.js";
import { writeFile } from "node:fs/promises";

globalThis.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(value => { this.result = value; this.onloadend?.(); }); }
  readAsDataURL(blob) { blob.arrayBuffer().then(value => { this.result = `data:${blob.type};base64,${Buffer.from(value).toString("base64")}`; this.onloadend?.(); }); }
};

const root = new THREE.Group(); root.name = "Ruijing_Aging_Line_20m";
const mat = (name, color, metalness=.1, opacity=1) => { const m = new THREE.MeshStandardMaterial({ color, metalness, roughness:.48, transparent:opacity<1, opacity }); m.name=name; return m; };
const white=mat("White sheet metal",0xe8edf0,.62), frame=mat("Steel frames",0x496171,.82), dark=mat("Conveyor",0x101c27,.65), glass=mat("Observation glass",0x142d40,.45,.48), red=mat("Red positioning rack",0xc82423,.52), adapter=mat("Adapter",0xeef3f5,.18);
const box=(name,x,y,z,m)=>{const o=new THREE.Mesh(new THREE.BoxGeometry(x,y,z),m);o.name=name;return o};
for(const z of [-1.1,1.1]){const o=box("Tunnel side wall",20,1.8,.08,white);o.position.set(10,.9,z);root.add(o)}const roof=box("Tunnel roof",20,.08,2.2,white);roof.position.set(10,1.8,0);root.add(roof);
for(let x=0;x<=20;x+=2)for(const z of [-1.12,1.12]){const o=box(`Frame ${x}m`,.055,1.86,.07,frame);o.position.set(x,.91,z);root.add(o)}
for(let i=0;i<7;i++){const o=box(`Observation window ${i+1}`,2.15,.035,1.15,glass);o.position.set(1.6+i*2.8,1.855,0);root.add(o)}
for(const [name,x] of [["Inlet conveyor",-1.25],["Outlet conveyor",21.25]]){const o=box(name,2.5,.24,1.25,dark);o.position.set(x,.05,0);root.add(o)}const ret=box("Carrier return conveyor",25,.12,.72,dark);ret.position.set(10,-.02,1.7);root.add(ret);
function carrier(index,x){const g=new THREE.Group();g.name=`20-slot carrier ${index}`;g.rotation.y=Math.PI/2;const base=box("Carrier base",1.6,.22,.55,white);base.position.y=.11;g.add(base);for(let i=0;i<5;i++){const r=box(`Red rack ${i+1}`,.035,.16,.48,red);r.position.set(-.62+i*.31,.29,0);g.add(r)}const ring=new THREE.Mesh(new THREE.TorusGeometry(.085,.015,10,28),dark);ring.name="Cooling fan";ring.rotation.x=Math.PI/2;ring.position.set(-.69,.25,0);g.add(ring);for(let i=0;i<20;i++){const a=box(`Adapter slot ${i+1}`,.145,.05,.06,adapter);a.position.set(-.71+(i%10)*.158,.31,(Math.floor(i/10)-.5)*.25);g.add(a)}g.position.set(x,.05,0);root.add(g)}
for(let i=0;i<6;i++)carrier(i+1,-1.2+i*3.8);
const result = await new GLTFExporter().parseAsync(root,{binary:true,onlyVisible:true});
await writeFile(new URL("./aging_line.glb",import.meta.url),Buffer.from(result));
console.log(`aging_line.glb ${result.byteLength} bytes`);
