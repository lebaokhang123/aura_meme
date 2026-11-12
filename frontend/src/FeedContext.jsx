import React, { createContext, useContext, useEffect, useState } from 'react';
import { filterUrl, readFilters } from './feed-data.js';
import { useLocalized } from './localize.jsx';
import { useSocial } from './SocialContext.jsx';
import { selectPosts } from './feed-data.js';

const FeedContext = createContext(null);
export const useFeed = () => useContext(FeedContext);
export function PostLink({ post, ...props }) {
  const render = useLocalized();
  const { url } = useFeed();
  return render(<a {...props} href={url('/', `post-${post.id}`)} aria-label={`Xem bài của ${post.authorName} trên Trang chủ`}>{post.authorName}</a>);
}
export function PostCategory({ post, ...props }) {
  const render = useLocalized();
  const { filters, update } = useFeed();
  return render(<a {...props} href={filterUrl(location.pathname, { ...filters, category: post.category })} onClick={event => {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); update({ category: post.category }); }
  }}>#{post.category}</a>);
}
export function FeedProvider({ children }) {
  const {posts,ready}=useSocial();
  const readTarget=()=>location.hash.match(/^#post-([\w-]+)$/)?.[1]||'';
  const [targetId,setTargetId]=useState(readTarget);
  const [filters, setFilters] = useState(() => readFilters(location.search));
  useEffect(() => {
    const restore = () => {setFilters(readFilters(location.search));setTargetId(readTarget())};
    addEventListener('popstate', restore);
    addEventListener('hashchange',restore);
    return () => {removeEventListener('popstate', restore);removeEventListener('hashchange',restore)};
  }, []);
  useEffect(()=>{
    if(!ready||!targetId||!posts.some(post=>post.id===targetId)||selectPosts(filters,posts).some(post=>post.id===targetId))return;
    const next={...filters,category:'',q:''};
    history.replaceState(null,'',filterUrl(location.pathname,next,location.hash));setFilters(next);
  },[ready,targetId,posts,filters]);
  const update = patch => {
    const next = { ...filters, ...patch };
    const path = ['/', '/explore'].includes(location.pathname) ? location.pathname : '/explore';
    const url = filterUrl(path, next);
    if (path !== location.pathname) { location.assign(url); return; }
    if (url !== location.pathname + location.search + location.hash) history.pushState(null, '', url);
    setTargetId('');
    setFilters(next);
  };
  return <FeedContext.Provider value={{ filters, update,targetId,missingPost:ready&&targetId&&!posts.some(post=>post.id===targetId), url: (path, hash) => filterUrl(path, filters, hash) }}>{children}</FeedContext.Provider>;
}
