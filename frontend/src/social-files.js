export const MAX_FILE_BYTES=5*1024*1024;
export const IMAGE_TYPES=['image/png','image/jpeg','image/gif'];
export function checkImageBytes(bytes,type,size,api=false) {
  if(!size||size>MAX_FILE_BYTES)throw Error('FILE_SIZE');
  if(!IMAGE_TYPES.includes(type)&&!(api&&type==='image/webp'))throw Error('FILE_TYPE');
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  let width,height;
  if(type==='image/png'){
    if(bytes.length<24||![137,80,78,71,13,10,26,10].every((n,i)=>bytes[i]===n))throw Error('FILE_TYPE');
    width=view.getUint32(16);height=view.getUint32(20);
  }else if(type==='image/gif'){
    const header=String.fromCharCode(...bytes.slice(0,6));
    if(bytes.length<10||!['GIF87a','GIF89a'].includes(header))throw Error('FILE_TYPE');
    width=view.getUint16(6,true);height=view.getUint16(8,true);
  }else if(type==='image/webp'){
    const text=(start,end)=>String.fromCharCode(...bytes.slice(start,end));
    if(bytes.length<25||text(0,4)!=='RIFF'||text(8,12)!=='WEBP'||view.getUint32(4,true)+8!==size)throw Error('FILE_TYPE');
    const format=text(12,16);
    if(format==='VP8X'&&bytes.length>=30){width=1+bytes[24]+(bytes[25]<<8)+(bytes[26]<<16);height=1+bytes[27]+(bytes[28]<<8)+(bytes[29]<<16);}
    else if(format==='VP8L'&&bytes[20]===47){const packed=view.getUint32(21,true);width=1+(packed&16383);height=1+((packed>>>14)&16383);}
    else if(format==='VP8 '&&bytes.length>=30&&bytes[23]===157&&bytes[24]===1&&bytes[25]===42){width=view.getUint16(26,true)&16383;height=view.getUint16(28,true)&16383;}
    else throw Error('FILE_TYPE');
  }else{
    if(bytes.length<4||bytes[0]!==255||bytes[1]!==216||bytes[2]!==255)throw Error('FILE_TYPE');
    let cursor=2;
    while(cursor+4<=bytes.length){
      if(bytes[cursor++]!==255)throw Error('FILE_TYPE');
      while(bytes[cursor]===255)cursor++;
      const marker=bytes[cursor++];
      if(marker===217||marker===218)break;
      if(marker===1||marker>=208&&marker<=215)continue;
      if(cursor+2>bytes.length)break;
      const length=view.getUint16(cursor);
      if(length<2||cursor+length>bytes.length)throw Error('FILE_TYPE');
      if([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)){
        if(length<7)throw Error('FILE_TYPE');height=view.getUint16(cursor+3);width=view.getUint16(cursor+5);break;
      }
      cursor+=length;
    }
  }
  if(!width||!height||(!api&&(width>8192||height>8192))||width*height>(api?12000000:25000000))throw Error('FILE_DIMENSIONS');
  return{width,height};
}
export async function validateImage(file,api=false) {
  if(!(file instanceof Blob))throw Error('FILE_TYPE');
  if(!file.size||file.size>MAX_FILE_BYTES)throw Error('FILE_SIZE');
  const dimensions=checkImageBytes(new Uint8Array(await file.arrayBuffer()),file.type,file.size,api);
  const url=URL.createObjectURL(file);
  try{
    await new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve();image.onerror=()=>reject(Error('FILE_DECODE'));image.src=url;});
    return dimensions;
  }finally{URL.revokeObjectURL(url)}
}
