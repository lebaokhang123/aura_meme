import React,{useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {auth,MOCK_AUTH} from '../auth.js';
import {authMessage} from '../auth-client.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {adminPage,canAdmin} from '../admin-api.js';
import '../workspace.css';

const sections=[['users','Người dùng','Users',['users']],['content','Nội dung','Content',['posts','comments','categories']],['contacts','Liên hệ','Contacts',['contacts']],['moderation','Kiểm duyệt','Moderation',['audit-logs','assets']]];
const labels={users:['Người dùng','Users'],posts:['Bài viết','Posts'],comments:['Bình luận','Comments'],categories:['Danh mục','Categories'],contacts:['Hộp thư liên hệ','Contact inbox'],'audit-logs':['Nhật ký kiểm duyệt','Audit log'],assets:['Trạng thái vật phẩm','Asset status']};
const states={users:['active','locked','deleted'],posts:['draft','published','hidden','deleted'],comments:['visible','hidden','deleted'],categories:['active','hidden'],contacts:['new','in_review','resolved'],assets:['pending','approved','rejected','unknown']};
const statusLabels={active:['Hoạt động','Active'],locked:['Đã khóa','Locked'],deleted:['Đã xóa','Deleted'],draft:['Bản nháp','Draft'],published:['Công khai','Published'],visible:['Hiển thị','Visible'],hidden:['Đã ẩn','Hidden'],new:['Mới','New'],in_review:['Đang xử lý','In review'],resolved:['Đã xử lý','Resolved'],pending:['Chờ duyệt','Pending'],approved:['Đã duyệt','Approved'],rejected:['Từ chối','Rejected'],unknown:['Chưa rõ','Unknown']};
export default function AdminPage(){
 const session=useSyncExternalStore(auth.subscribe,auth.snapshot),{language}=usePreferences(),t=(vi,en)=>language==='en'?en:vi;
 const title=resource=>t(...labels[resource]),status=value=>statusLabels[value]?t(...statusLabels[value]):value;
 const allowed=!MOCK_AUTH&&session.status==='authenticated'&&canAdmin(session.user),owner=allowed?session.user.id:null;
 const [resource,setResource]=useState('users'),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[filter,setFilter]=useState(''),[role,setRole]=useState(''),[page,setPage]=useState(1),[revision,setRevision]=useState(0);
 const [result,setData]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState(''),[success,setSuccess]=useState(''),[denied,setDenied]=useState(false),[edit,setEdit]=useState(null),[busy,setBusy]=useState(false);
 const dialog=useRef(null),inflight=useRef(false),currentOwner=useRef(owner);currentOwner.current=owner;
 // Never render a previous resource or account while the next read is pending.
 const data=result?.resource===resource&&result.owner===owner?result:null;
 const section=sections.find(row=>row[3].includes(resource));
 const explain=e=>e.status===409&&resource==='users'?t('Thay đổi bị từ chối. Phải giữ ít nhất một Admin đang hoạt động.','Change refused. At least one active Admin must remain.'):authMessage(e,language);
 useEffect(()=>{setDenied(false);setData(null);setEdit(null);setError('');setSuccess('');},[owner]);
 useEffect(()=>{
  setData(null);setError('');if(!allowed)return;let active=true;setLoading(true);
  const params=new URLSearchParams({page:String(page),page_size:'20'});if(search)params.set('search',search);if(filter)params.set(resource==='assets'?'review_status':'status',filter);if(resource==='users'&&role)params.set('role',role);
  auth.read('/admin/'+resource+'?'+params).then(value=>adminPage(value,resource)).then(value=>{if(active)setData({...value,resource,owner})}).catch(e=>{if(active){setError(explain(e));if(e.status===403){setDenied(true);auth.refresh().catch(()=>{})}if(e.status===401)auth.refresh().catch(()=>{});}}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[allowed,owner,resource,search,filter,role,page,revision]);
 useEffect(()=>{if(edit&&!dialog.current?.open)dialog.current.showModal();else if(!edit)dialog.current?.close()},[edit]);
 function choose(value){setResource(value);setPage(1);setQuery('');setSearch('');setFilter('');setRole('');setError('');setSuccess('');}
 function confirm(row,body,label,path='/admin/'+resource+'/'+row.id){setError('');setEdit({type:'confirm',row,body,label,path,method:'PATCH'})}
 async function save(event){
  event.preventDefault();if(inflight.current||!edit)return;inflight.current=true;setBusy(true);setError('');setSuccess('');const requestOwner=owner;
  let method=edit.method||'PATCH',path=edit.path||'/admin/'+resource+'/'+(edit.row?.id||''),body=edit.body;
  if(edit.type==='roles'){method='PUT';path='/admin/users/'+edit.row.id+'/roles';body={roles:edit.roles}}
  if(edit.type==='category'){method=edit.row?'PATCH':'POST';path='/admin/categories'+(edit.row?'/'+edit.row.id:'');body=edit.row?{name:edit.name,status:edit.status}:{name:edit.name,slug:edit.slug};}
  if(edit.type==='contact'){path='/admin/contacts/'+edit.row.id;body={status:edit.status}}
  try{await auth.write(method,path,body);if(currentOwner.current!==requestOwner)return;setEdit(null);setRevision(n=>n+1);setSuccess(t('Đã lưu thay đổi.','Changes saved.'));if(resource==='users'&&edit.row?.id===requestOwner)await auth.refresh().catch(()=>{});}
  catch(e){if(currentOwner.current===requestOwner){setError(explain(e));if(e.status===403){setData(null);setDenied(true);setEdit(null);auth.refresh().catch(()=>{})}}}
  finally{inflight.current=false;setBusy(false)}
 }
 const stamp=value=>new Date(value).toLocaleString(language==='en'?'en-GB':'vi-VN');
 if(!allowed||denied)return <main className="workspace-page"><div className="workspace-content"><section className="workspace-panel" role="alert"><h1>{t('Không có quyền truy cập','Access denied')}</h1><p>{t('Trang này chỉ dành cho Admin do máy chủ xác minh.','This workspace requires an Admin role verified by the server.')}</p><a href="/">{t('Quay lại Trang chủ','Back to Home')}</a></section></div></main>;
 return <main className="workspace-page admin-page"><div className="workspace-content">
  <header className="workspace-hero"><span className="workspace-kicker">AURAMEME</span><h1>{t('Không gian quản trị','Admin Workspace')}</h1><p>{t('Quản lý cộng đồng bằng các thao tác rõ ràng, có lưu vết.','Manage the community with clear, audited actions.')}</p></header>
  <nav className="workspace-tabs" aria-label={t('Khu quản trị','Admin sections')}>{sections.map(([id,vi,en,resources])=><button type="button" key={id} aria-current={section[0]===id?'page':undefined} onClick={()=>choose(resources[0])}>{t(vi,en)}</button>)}</nav>
  {section[3].length>1&&<nav className="workspace-subtabs" aria-label={t('Chức năng quản trị','Admin tools')}>{section[3].map(value=><button type="button" key={value} aria-pressed={resource===value} onClick={()=>choose(value)}>{title(value)}</button>)}</nav>}
  <section className="workspace-panel" aria-labelledby="admin-list-title"><div className="workspace-panel-heading"><h2 id="admin-list-title">{title(resource)}</h2>{resource==='categories'&&<button type="button" className="workspace-primary" onClick={()=>{setError('');setEdit({type:'category',row:null,name:'',slug:''})}}>{t('Thêm danh mục','Add category')}</button>}</div>
   <form className="workspace-filters" role="search" aria-label={t('Tìm trong khu quản trị','Search Admin Workspace')} onSubmit={e=>{e.preventDefault();setSearch(query.trim());setPage(1)}}><label>{t('Tìm kiếm','Search')}<input type="search" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} /></label>{states[resource]&&<label>{t('Trạng thái','Status')}<select value={filter} onChange={e=>{setFilter(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option>{states[resource].map(v=><option key={v} value={v}>{status(v)}</option>)}</select></label>}{resource==='users'&&<label>{t('Vai trò','Role')}<select value={role} onChange={e=>{setRole(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option><option>USER</option><option>ADMIN</option></select></label>}<button type="submit">{t('Tìm','Search')}</button></form>
   {error&&!edit&&<div className="workspace-error" role="alert">{error}<button type="button" onClick={()=>setRevision(n=>n+1)}>{t('Thử lại','Retry')}</button></div>}{success&&<p role="status" className="workspace-success">{success}</p>}
   {loading?<p role="status">{t('Đang tải…','Loading…')}</p>:data&&!data.items.length?<p>{t('Không có dữ liệu phù hợp.','No matching records.')}</p>:<div className="workspace-rows">{data?.items.map(row=><article className="workspace-row" key={row.id} data-admin-id={row.id}><div className="workspace-row-main">
    {resource==='users'&&<><h3>{row.display_name}</h3><p translate="no">@{row.username}</p><p className="workspace-meta">{row.roles.join(' · ')||t('Chưa có vai trò','No role')}</p></>}
    {(resource==='posts'||resource==='comments')&&<><h3>{resource==='posts'?row.title:'@'+row.author.username}</h3><p className="workspace-meta">@{row.author.username} · {stamp(row.created_at)}</p><details><summary>{t('Xem nội dung','View content')}</summary><p className="workspace-text" translate="no">{row.content??row.body}</p>{row.media_url&&row.status!=='deleted'&&<a href={'/api/v1/admin/posts/'+row.id+'/media'} target="_blank" rel="noopener noreferrer">{t('Xem ảnh bài viết','View post image')}</a>}<a href={'/#post-'+(row.post_id||row.id)}>{t('Mở bài viết','Open post')}</a></details></>}
    {resource==='categories'&&<><h3>{row.name}</h3><p className="workspace-meta">{row.slug}</p></>}
    {resource==='contacts'&&<><h3>{row.subject}</h3><p>{row.name}</p><p className="workspace-meta">{stamp(row.created_at)}</p></>}
    {resource==='assets'&&<><h3>{row.slug}</h3><p className="workspace-meta">{row.kind} · {row.rarity} · {status(row.review_status)}</p></>}
    {resource==='audit-logs'&&<><h3>{row.action}</h3><p className="workspace-meta">{row.target_type} · {row.target_id}</p><p className="workspace-meta">{t('Người thực hiện','Actor')}: {row.actor_id} · {stamp(row.created_at)}</p></>}
   </div><div className="workspace-row-actions">
    {row.status&&<span className="workspace-badge" data-status={row.status}>{status(row.status)}</span>}{resource==='assets'&&<span className="workspace-badge">{row.active?t('Đang bật','Active'):t('Đang tắt','Inactive')}</span>}
    {resource==='users'&&row.status!=='deleted'&&<><button type="button" disabled={busy} onClick={()=>confirm(row,{status:row.status==='active'?'locked':'active'},row.status==='active'?t('Khóa tài khoản','Lock account'):t('Mở khóa tài khoản','Unlock account'))}>{row.status==='active'?t('Khóa','Lock'):t('Mở khóa','Unlock')}</button><button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'roles',row,roles:[...row.roles]})}}>{t('Sửa vai trò','Edit roles')}</button></>}
    {(resource==='posts'||resource==='comments')&&row.status!=='deleted'&&<button type="button" disabled={busy} onClick={()=>confirm(row,{status:row.status==='hidden'?(resource==='posts'?'published':'visible'):'hidden'},row.status==='hidden'?t('Hiển thị nội dung','Show content'):t('Ẩn nội dung','Hide content'))}>{row.status==='hidden'?t('Hiển thị','Show'):t('Ẩn','Hide')}</button>}
    {resource==='categories'&&<button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'category',row,name:row.name,status:row.status})}}>{t('Chỉnh sửa','Edit')}</button>}
    {resource==='contacts'&&<button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'contact',row,status:row.status})}}>{t('Xem và xử lý','View and update')}</button>}
   </div></article>)}</div>}
   {data&&<nav className="workspace-pagination" aria-label={t('Phân trang quản trị','Admin pagination')}><button type="button" disabled={loading||page<=1} onClick={()=>setPage(n=>n-1)}>{t('Trước','Previous')}</button><span>{page} / {Math.max(1,data.pagination.total_pages)} · {data.pagination.total} {t('mục','records')}</span><button type="button" disabled={loading||page>=data.pagination.total_pages} onClick={()=>setPage(n=>n+1)}>{t('Sau','Next')}</button></nav>}
  </section>
  <dialog ref={dialog} className="workspace-dialog" aria-labelledby="admin-dialog-title" onCancel={e=>{if(busy)e.preventDefault();else setEdit(null)}} onClose={()=>setEdit(null)}>{edit&&<form onSubmit={save}><div className="workspace-panel-heading"><h2 id="admin-dialog-title">{edit.type==='roles'?t('Sửa vai trò','Edit roles'):edit.type==='category'?t('Danh mục','Category'):edit.type==='contact'?t('Xử lý liên hệ','Update contact'):edit.label}</h2><button type="button" aria-label={t('Đóng','Close')} disabled={busy} onClick={()=>setEdit(null)}>×</button></div>
   {edit.type==='confirm'&&<p>{t('Xác nhận thao tác này?','Confirm this action?')}</p>}
   {edit.type==='roles'&&<><p>@{edit.row.username}</p><fieldset><legend>{t('Vai trò từ DB','Database roles')}</legend>{['USER','ADMIN'].map(value=><label className="workspace-checkbox" key={value}><input type="checkbox" checked={edit.roles.includes(value)} disabled={busy} onChange={e=>setEdit({...edit,roles:e.target.checked?[...edit.roles,value]:edit.roles.filter(r=>r!==value)})}/>{value}</label>)}</fieldset><p className="workspace-meta">{t('Thay đổi vai trò sẽ kết thúc các phiên của tài khoản đó.','Changing roles ends that account’s sessions.')}</p></>}
   {edit.type==='category'&&<><label>{t('Tên danh mục','Category name')}<input value={edit.name} maxLength={80} required disabled={busy} onChange={e=>setEdit({...edit,name:e.target.value})}/></label>{!edit.row?<label>Slug<input value={edit.slug} maxLength={80} pattern="[a-z0-9-]+" required disabled={busy} onChange={e=>setEdit({...edit,slug:e.target.value})}/></label>:<label>{t('Trạng thái','Status')}<select value={edit.status} disabled={busy} onChange={e=>setEdit({...edit,status:e.target.value})}>{states.categories.map(v=><option value={v} key={v}>{status(v)}</option>)}</select></label>}</>}
   {edit.type==='contact'&&<><h3>{edit.row.subject}</h3><p>{edit.row.name}</p><p className="workspace-text" translate="no">{edit.row.body}</p><label>{t('Trạng thái','Status')}<select value={edit.status} disabled={busy} onChange={e=>setEdit({...edit,status:e.target.value})}>{states.contacts.map(v=><option value={v} key={v}>{status(v)}</option>)}</select></label></>}
   {error&&<p className="workspace-error" role="alert">{error}</p>}<div className="workspace-dialog-actions"><button type="button" disabled={busy} onClick={()=>setEdit(null)}>{t('Hủy','Cancel')}</button><button type="submit" className="workspace-primary" disabled={busy}>{busy?t('Đang lưu…','Saving…'):t('Xác nhận','Confirm')}</button></div>
  </form>}</dialog>
 </div></main>;
}
