// Reuse approved Stitch body and picker markup; social state lives outside these templates.
import React from 'react';
import * as views from './feed-post-views.js';
import {POSTS} from '../feed-data.js';
import baseline from '../social-baseline.json' with {type:'json'};
const elements=tree=>React.Children.toArray(tree.props.children).filter(child=>React.isValidElement(child));
const walk=(node,test)=>{
  if(Array.isArray(node)){for(const child of node){const result=walk(child,test);if(result)return result;}return null;}
  if(!React.isValidElement(node))return null;
  return test(node)?node:walk(node.props.children,test);
};
export function OriginalBody({post,variant='home'}) {
  const index=POSTS.findIndex(sample=>sample.id===post.id);
  if(index<0)return null;
  const children=elements(views[variant+index]({post}));
  return <>{children.slice(1,index===1?2:3)}</>;
}
const classCache=new Map();
export function authorClasses(author,comment=false) {
  const key=author+(comment?'-comment':'');if(classCache.has(key))return classCache.get(key);
  const id={Khang_dev:'khang',Kien_dev:'kien',Gigachad:'gigachad'}[author]||'khang';
  const sample=POSTS.find(post=>post.id===id),tree=views['home'+POSTS.indexOf(sample)]({post:sample});
  const label=node=>React.Children.toArray(node.props.children).filter(c=>typeof c==='string').join('').trim();
  let scope=tree;
  if(comment){
    const record=baseline.comments.find(c=>c.author===author);
    const root=views['home'+POSTS.findIndex(p=>p.id===record.postId)]({post:POSTS.find(p=>p.id===record.postId)});
    const path=[];
    const find=(node,parents=[])=>{if(Array.isArray(node)){for(const child of node)if(find(child,parents))return true;return false;}if(!React.isValidElement(node))return false;if(node.type==='p'&&label(node)===record.text){path.push(...parents,node);return true;}return find(node.props.children,[...parents,node]);};
    find(root);
    scope=[...path].reverse().find(node=>walk(node,n=>label(n)===sample.level)&&walk(node,n=>label(n)===sample.nickname))||root;
  }
  const result={level:walk(scope,n=>label(n)===sample.level)?.props.className,nickname:walk(scope,n=>label(n)===sample.nickname)?.props.className};classCache.set(key,result);return result;
}
export function PickerMarkup() {
  const tree=views.home0({post:POSTS[0]});
  const picker=walk(tree,n=>n.props.id==='reaction-popover');
  return React.cloneElement(picker,{className:picker.props.className.replace(/\babsolute\b|\bbottom-full\b|\bleft-0\b|\bmb-\d+\b|\bhidden\b|\bz-\d+\b|w-\[\d+px\]/g,'')+' relative w-full',id:undefined});
}
export function OriginalComments({post}) {
  const index=POSTS.findIndex(sample=>sample.id===post.id);
  if(index<0||index===2)return null;
  return elements(views['home'+index]({post})).at(-1);
}
