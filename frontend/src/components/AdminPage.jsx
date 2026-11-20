import React,{useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {auth,MOCK_AUTH} from '../auth.js';
import {authMessage} from '../auth-client.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {adminPage,canAdmin} from '../admin-api.js';
import '../workspace.css';

const sections=[['users','Người dùng','Users',['users']],['content','Nội dung','Content',['posts','comments','categories']],['contacts','Liên hệ','Contacts',['contacts']],['moderation','Kiểm duyệt','Moderation',['audit-logs','assets']],['notifications','Thông báo','Notifications',['announcements']]];
const labels={users:['Người dùng','Users'],posts:['Bài viết','Posts'],comments:['Bình luận','Comments'],categories:['Danh mục','Categories'],contacts:['Hộp thư liên hệ','Contact inbox'],'audit-logs':['Nhật ký quản trị','Admin activity'],assets:['Trạng thái vật phẩm','Asset status'],announcements:['Thông báo hệ thống','System announcements']};
const sectionIcons={users:'group',content:'article',contacts:'inbox',moderation:'shield',notifications:'campaign'};
const resourceNotes={users:['Quản lý trạng thái và quyền truy cập của thành viên.','Manage member status and access.'],posts:['Xem nội dung và kiểm soát những bài xuất hiện trong cộng đồng.','Review posts and control their visibility in the community.'],comments:['Xem và xử lý bình luận, kể cả nội dung đã ẩn.','Review comments, including hidden content.'],categories:['Sắp xếp nội dung bằng các danh mục dùng chung.','Organize community content with shared categories.'],contacts:['Đọc và phân loại tin nhắn gửi đến AuraMeme.','Read and triage messages sent to AuraMeme.'],'audit-logs':['Ghi lại các thay đổi do quản trị viên thực hiện: ai đã làm gì và khi nào.','Log of administrative actions: who did what and when.'],assets:['Kiểm tra trạng thái hoạt động và duyệt của danh mục vật phẩm.','Inspect catalog availability and review status.'],announcements:['Soạn thảo, quản lý và phát thông báo tới các thành viên.','Draft, manage, and broadcast announcements to community members.']};
const Icon=({name,...props})=><span className="material-symbols-outlined" aria-hidden="true" {...props}>{name}</span>;
const states={users:['active','locked','deleted'],posts:['draft','published','hidden','deleted'],comments:['visible','hidden','deleted'],categories:['active','hidden'],contacts:['new','in_review','resolved'],assets:['pending','approved','rejected','unknown'],announcements:['draft','published','withdrawn']};
const auditActionLabels={
  'contact.update':['Cập nhật trạng thái liên hệ','Updated contact status'],
  'post.update':['Cập nhật bài viết','Updated post'],
  'post.hidden':['Ẩn bài viết','Hidden post'],
  'post.deleted':['Xóa bài viết','Deleted post'],
  'post.delete':['Xóa bài viết','Deleted post'],
  'comment.hidden':['Ẩn bình luận','Hidden comment'],
  'comment.deleted':['Xóa bình luận','Deleted comment'],
  'comment.update':['Cập nhật bình luận','Updated comment'],
  'announcement.create':['Tạo thông báo hệ thống','Created system announcement'],
  'announcement.publish':['Phát thông báo hệ thống','Broadcasted system announcement'],
  'announcement.withdraw':['Thu hồi thông báo hệ thống','Withdrew system announcement'],
  'announcement.delete':['Xóa thông báo hệ thống','Deleted announcement'],
  'user.status':['Cập nhật trạng thái người dùng','Updated user status'],
  'user.roles':['Cập nhật vai trò người dùng','Updated user roles'],
  'category.create':['Tạo danh mục','Created category'],
  'category.update':['Cập nhật danh mục','Updated category'],
  'asset.review':['Kiểm duyệt vật phẩm','Reviewed asset'],
  'asset.update':['Cập nhật vật phẩm','Updated asset']
};
const auditTargetLabels={
  post:['Bài viết','Post'],
  comment:['Bình luận','Comment'],
  contact:['Liên hệ','Contact message'],
  announcement:['Thông báo','Announcement'],
  user:['Người dùng','User'],
  category:['Danh mục','Category'],
  asset:['Vật phẩm','Asset']
};
const statusLabels={active:['Hoạt động','Active'],locked:['Đã khóa','Locked'],deleted:['Đã xóa','Deleted'],draft:['Bản nháp','Draft'],published:['Công khai','Published'],visible:['Hiển thị','Visible'],hidden:['Đã ẩn','Hidden'],new:['Mới','New'],in_review:['Đang xử lý','In review'],resolved:['Đã xử lý','Resolved'],pending:['Chờ duyệt','Pending'],approved:['Đã duyệt','Approved'],rejected:['Từ chối','Rejected'],unknown:['Chưa rõ','Unknown'],withdrawn:['Đã thu hồi','Withdrawn']};
export default function AdminPage(){
 const session=useSyncExternalStore(auth.subscribe,auth.snapshot),{language}=usePreferences(),t=(vi,en)=>language==='en'?en:vi;
 const title=resource=>t(...labels[resource]),status=value=>statusLabels[value]?t(...statusLabels[value]):value,formatAuditAction=a=>auditActionLabels[a]?t(...auditActionLabels[a]):a,formatAuditTarget=trg=>auditTargetLabels[trg]?t(...auditTargetLabels[trg]):trg;
 const allowed=!MOCK_AUTH&&session.status==='authenticated'&&canAdmin(session.user),owner=allowed?session.user.id:null;
 const [resource,setResource]=useState('users'),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[filter,setFilter]=useState(''),[role,setRole]=useState(''),[page,setPage]=useState(1),[revision,setRevision]=useState(0);
 const [result,setData]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState(''),[success,setSuccess]=useState(''),[denied,setDenied]=useState(false),[edit,setEdit]=useState(null),[busy,setBusy]=useState(false),[holdingPreview,setHoldingPreview]=useState(false),[copiedId,setCopiedId]=useState(null);
 const dialog=useRef(null),inflight=useRef(false),currentOwner=useRef(owner);currentOwner.current=owner;
 // Never render a previous resource or account while the next read is pending.
 const data=result?.resource===resource&&result.owner===owner?result:null;
 const section=sections.find(row=>row[3].includes(resource));
 const explain=e=>e.status===409&&resource==='users'?t('Thay đổi bị từ chối. Phải giữ ít nhất một Admin đang hoạt động.','Change refused. At least one active Admin must remain.'):authMessage(e,language);
 useEffect(()=>{setDenied(false);setData(null);setEdit(null);setHoldingPreview(false);setError('');setSuccess('');},[owner]);
 useEffect(()=>{
  setData(null);setError('');if(!allowed)return;let active=true;setLoading(true);
  const params=new URLSearchParams({page:String(page),page_size:'20'});if(search)params.set('search',search);if(filter)params.set(resource==='assets'?'review_status':'status',filter);if(resource==='users'&&role)params.set('role',role);
  auth.read('/admin/'+resource+'?'+params).then(value=>adminPage(value,resource)).then(value=>{if(active)setData({...value,resource,owner})}).catch(e=>{if(active){setError(explain(e));if(e.status===403){setDenied(true);auth.refresh().catch(()=>{})}if(e.status===401)auth.refresh().catch(()=>{});}}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[allowed,owner,resource,search,filter,role,page,revision]);
 useEffect(()=>{if(edit&&!dialog.current?.open)dialog.current.showModal();else if(!edit){dialog.current?.close();setHoldingPreview(false);}},[edit]);
 function choose(value){setResource(value);setPage(1);setQuery('');setSearch('');setFilter('');setRole('');setError('');setSuccess('');}
 function confirm(row,body,label,path='/admin/'+resource+'/'+row.id,method='PATCH'){setError('');setEdit({type:'confirm',row,body,label,path,method})}
 async function save(event){
  event.preventDefault();if(edit?.type==='content-preview'){setEdit(null);return;}if(inflight.current||!edit)return;inflight.current=true;setBusy(true);setError('');setSuccess('');const requestOwner=owner;
  let method=edit.method||'PATCH',path=edit.path||'/admin/'+resource+'/'+(edit.row?.id||''),body=edit.body;
  if(edit.type==='roles'){method='PUT';path='/admin/users/'+edit.row.id+'/roles';body={roles:edit.roles}}
  if(edit.type==='category'){method=edit.row?'PATCH':'POST';path='/admin/categories'+(edit.row?'/'+edit.row.id:'');body=edit.row?{name:edit.name,status:edit.status}:{name:edit.name,slug:edit.slug};}
  if(edit.type==='contact'){path='/admin/contacts/'+edit.row.id;body={status:edit.status}}
  if(edit.type==='announcement'){
    if(edit.draft){
      if(edit.row){method='PATCH';path='/admin/announcements/'+edit.row.id;body={title:edit.title.trim(),body:edit.body.trim()}}
      else{method='POST';path='/admin/announcements';body={title:edit.title.trim(),body:edit.body.trim(),is_draft:true}}
    }else{
      if(edit.row&&edit.row.status==='draft'){method='POST';path='/admin/announcements/'+edit.row.id+'/publish';body={}}
      else{method='POST';path='/admin/announcements';body={title:edit.title.trim(),body:edit.body.trim(),is_draft:false}}
    }
  }
  if(edit.type==='moderate'){
    if(!edit.reason||edit.reason.trim().length<5){
      setError(t('Vui lòng nhập lý do kiểm duyệt tối thiểu 5 ký tự.','Please enter a moderation reason of at least 5 characters.'));
      inflight.current=false;setBusy(false);return;
    }
    method='PATCH';
    path='/admin/'+edit.targetResource+'/'+edit.row.id;
    body={status:edit.action,reason:edit.reason.trim()};
  }
  try{await auth.write(method,path,body);if(currentOwner.current!==requestOwner)return;setEdit(null);setRevision(n=>n+1);setSuccess(t('Đã lưu thay đổi.','Changes saved.'));if(resource==='users'&&edit.row?.id===requestOwner)await auth.refresh().catch(()=>{});}
  catch(e){if(currentOwner.current===requestOwner){setError(explain(e));if(e.status===403){setData(null);setDenied(true);setEdit(null);auth.refresh().catch(()=>{})}}}
  finally{inflight.current=false;setBusy(false)}
 }
 const copyTargetId=id=>{if(navigator?.clipboard?.writeText){navigator.clipboard.writeText(id).then(()=>{setCopiedId(id);setTimeout(()=>setCopiedId(null),2000)}).catch(()=>{})}};
 const stamp=value=>new Date(value).toLocaleString(language==='en'?'en-GB':'vi-VN');
 if(!allowed||denied)return <main className="workspace-page"><div className="workspace-content"><section className="workspace-panel" role="alert"><h1>{t('Không có quyền truy cập','Access denied')}</h1><p>{t('Trang này chỉ dành cho Admin do máy chủ xác minh.','This workspace requires an Admin role verified by the server.')}</p><a href="/">{t('Quay lại Trang chủ','Back to Home')}</a></section></div></main>;
 return <main className="workspace-page admin-page"><div className="workspace-content admin-layout">
  <aside className="admin-sidebar">
   <div className="admin-workspace-brand"><span className="admin-brand-mark"><Icon name="shield"/></span><div><strong>AuraMeme</strong><span>Workspace</span></div></div>
   <p className="admin-nav-caption">{t('QUẢN LÝ CỘNG ĐỒNG','COMMUNITY MANAGEMENT')}</p>
   <nav className="workspace-tabs" aria-label={t('Khu quản trị','Admin sections')}>{sections.map(([id,vi,en,resources])=><button type="button" key={id} aria-current={section[0]===id?'page':undefined} onClick={()=>choose(resources[0])}><Icon name={sectionIcons[id]}/><span>{t(vi,en)}</span><Icon name="chevron_right" className="material-symbols-outlined admin-nav-arrow"/></button>)}</nav>
   <div className="admin-sidebar-bottom"><div className="admin-access-note"><Icon name="verified_user"/><div><strong>{t('Quyền quản trị','Admin access')}</strong><p>{t('Mọi thay đổi đều được kiểm tra quyền và lưu vết.','Changes are permission-checked and audited.')}</p></div></div><a className="admin-home-link" href="/"><Icon name="arrow_back"/>{t('Về Trang chủ','Back to Home')}</a></div>
  </aside>
  <div className="admin-main">
  <header className="admin-heading"><div><p className="admin-breadcrumb">Workspace <Icon name="chevron_right"/>{t(section[1],section[2])}</p><h1>{t('Không gian quản trị','Admin Workspace')}</h1></div><span className="admin-session-badge"><span/>{t('Phiên Admin','Admin session')}</span></header>
  {section[3].length>1&&<nav className="workspace-subtabs" aria-label={t('Chức năng quản trị','Admin tools')}>{section[3].map(value=><button type="button" key={value} aria-pressed={resource===value} onClick={()=>choose(value)}>{title(value)}</button>)}</nav>}
  <section className="workspace-panel admin-list-panel" aria-labelledby="admin-list-title" data-resource={resource}><div className="workspace-panel-heading"><div><div className="admin-list-title"><h2 id="admin-list-title">{title(resource)}</h2>{data&&<span className="admin-count" aria-label={t('Tổng số mục','Total records')}>{data.pagination.total}</span>}</div><p className="admin-list-note">{t(...resourceNotes[resource])}</p></div><div className="admin-toolbar-actions"><button type="button" className="admin-refresh" disabled={loading||busy} aria-label={t('Tải lại danh sách','Refresh list')} onClick={()=>setRevision(n=>n+1)}><Icon name="refresh"/></button>{resource==='announcements'&&<button type="button" className="workspace-primary admin-broadcast-btn" disabled={loading||busy} onClick={()=>{setError('');setEdit({type:'announcement',row:null,title:'',body:'',mode:'compose'})}}><Icon name="campaign"/>{t('Phát thông báo','Broadcast')}</button>}{resource==='categories'&&<button type="button" className="workspace-primary" onClick={()=>{setError('');setEdit({type:'category',row:null,name:'',slug:''})}}><Icon name="add"/>{t('Thêm danh mục','Add category')}</button>}</div></div>
   <form className="workspace-filters" role="search" aria-label={t('Tìm trong khu quản trị','Search Admin Workspace')} onSubmit={e=>{e.preventDefault();setSearch(query.trim());setPage(1)}}><label>{t('Tìm kiếm','Search')}<input type="search" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} /></label>{states[resource]&&<label>{t('Trạng thái','Status')}<select value={filter} onChange={e=>{setFilter(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option>{states[resource].map(v=><option key={v} value={v}>{status(v)}</option>)}</select></label>}{resource==='users'&&<label>{t('Vai trò','Role')}<select value={role} onChange={e=>{setRole(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option><option>USER</option><option>ADMIN</option></select></label>}<button type="submit" className="admin-search-button"><Icon name="search"/>{t('Tìm','Search')}</button></form>
   {error&&!edit&&<div className="workspace-error" role="alert">{error}<button type="button" onClick={()=>setRevision(n=>n+1)}>{t('Thử lại','Retry')}</button></div>}{success&&<p role="status" className="workspace-success">{success}</p>}
   <div className="admin-column-head" aria-hidden="true"><span>{resource==='users'?t('Thành viên / Vai trò','Member / Role'):title(resource)}</span><span>{resource==='audit-logs'?t('Thời gian','Time'):t('Trạng thái','Status')}</span><span>{resource==='audit-logs'?'':t('Thao tác','Actions')}</span></div>
   {loading?<div className="admin-loading" role="status" aria-busy="true"><span className="workspace-sr">{t('Đang tải…','Loading…')}</span>{[0,1,2].map(n=><div className="admin-skeleton-row" key={n} aria-hidden="true"><span/><div><i/><i/></div><b/></div>)}</div>:data&&!data.items.length?<div className="admin-empty"><Icon name="search_off"/><h3>{t('Không có dữ liệu phù hợp.','No matching records.')}</h3><p>{t('Thử thay đổi từ khóa hoặc bỏ bộ lọc.','Try a different search or clear the filters.')}</p>{(search||filter||role)&&<button type="button" onClick={()=>choose(resource)}>{t('Xóa bộ lọc','Clear filters')}</button>}</div>:<div className="workspace-rows" key={resource}>{data?.items.map(row=><article className="workspace-row" key={row.id} data-admin-id={row.id}><div className="workspace-row-main">
    {resource==='users'&&<div className="admin-identity"><span className="admin-initial" aria-hidden="true">{row.display_name.trim().slice(0,1).toUpperCase()||'@'}</span><div><h3 translate="no">{row.display_name}</h3><p translate="no">@{row.username}</p><p className="admin-role-list">{row.roles.length?row.roles.map(value=><span key={value} data-role={value}>{value}</span>):t('Chưa có vai trò','No role')}</p></div></div>}
    {(resource==='posts'||resource==='comments')&&<><h3>{resource==='posts'?row.title:'@'+row.author.username}</h3><p className="workspace-meta">@{row.author.username} · {stamp(row.created_at)}</p><p className="admin-content-snippet" translate="no">{(row.content??row.body)?.length>120?((row.content??row.body).slice(0,120)+'…'):(row.content??row.body)}</p></>}
    {resource==='categories'&&<><h3>{row.name}</h3><p className="workspace-meta">{row.slug}</p></>}
    {resource==='contacts'&&<><h3>{row.subject}</h3><p>{row.name}</p><p className="workspace-meta">{stamp(row.created_at)}</p></>}
    {resource==='assets'&&<><h3>{row.slug}</h3><p className="workspace-meta">{row.kind} · {row.rarity} · {status(row.review_status)}</p></>}
    {resource==='audit-logs'&&<div className="admin-audit-entry">
      <div className="admin-audit-entry-header">
        <span className="admin-audit-action-badge"><Icon name="history_toggle_off"/></span>
        <div>
          <h3 className="admin-audit-title">{formatAuditAction(row.action)}</h3>
          <p className="admin-audit-sub">
            <span>{t('Thực hiện: ','By: ')}<strong>{row.actor_id===owner?t('Bạn (Admin hiện tại)','You (Current Admin)'):(t('Quản trị viên #','Admin #')+String(row.actor_id).slice(0,8))}</strong></span>
            <span>·</span>
            <span>{t('Đối tượng: ','Target: ')}<strong>{formatAuditTarget(row.target_type)}</strong></span>
          </p>
        </div>
      </div>
      <details className="admin-audit-tech-details">
        <summary>{t('Chi tiết kỹ thuật','Technical details')}</summary>
        <div className="admin-audit-id-copy">
          <code>{row.target_type} ID: {row.target_id}</code>
          <button type="button" className="admin-copy-btn" onClick={()=>copyTargetId(row.target_id)} aria-label={t('Sao chép mã định danh','Copy technical ID')} title={t('Sao chép mã định danh','Copy technical ID')}>
            <Icon name={copiedId===row.target_id?"check":"content_copy"}/>
            <span>{copiedId===row.target_id?t('Đã sao chép','Copied'):t('Sao chép','Copy')}</span>
          </button>
        </div>
      </details>
    </div>}
    {resource==='announcements'&&<><h3>{row.title}</h3><p className="workspace-meta">@{row.actor_username||'admin'} · {stamp(row.created_at)}</p><details><summary>{t('Xem nội dung','View content')}</summary><p className="workspace-text" translate="no">{row.body}</p>{row.published_at&&<p className="workspace-meta">{t('Phát lúc:','Broadcasted at:')} {stamp(row.published_at)} · {row.recipients_count} {t('người nhận','recipients')}</p>}</details></>}
   </div><div className="admin-row-status">
    {resource==='audit-logs'&&<time className="workspace-meta" dateTime={row.created_at}>{stamp(row.created_at)}</time>}
    {row.status&&<span className="workspace-badge" data-status={row.status}>{status(row.status)}</span>}{resource==='assets'&&<span className="workspace-badge">{row.active?t('Đang bật','Active'):t('Đang tắt','Inactive')}</span>}
    </div><div className="workspace-row-actions">{resource==='users'&&row.status!=='deleted'&&<><button type="button" disabled={busy} onClick={()=>confirm(row,{status:row.status==='active'?'locked':'active'},row.status==='active'?t('Khóa tài khoản','Lock account'):t('Mở khóa tài khoản','Unlock account'))}>{row.status==='active'?t('Khóa','Lock'):t('Mở khóa','Unlock')}</button><button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'roles',row,roles:[...row.roles]})}}>{t('Sửa vai trò','Edit roles')}</button></>}
    {(resource==='posts'||resource==='comments')&&<div className="admin-action-icons">
      <button type="button" className="admin-icon-btn" disabled={busy} aria-label={resource==='posts'?t('Xem chi tiết bài viết','View post details'):t('Xem chi tiết bình luận','View comment details')} title={resource==='posts'?t('Xem chi tiết bài viết','View post details'):t('Xem chi tiết bình luận','View comment details')} onClick={()=>{setError('');setEdit({type:'content-preview',row,targetResource:resource})}}><Icon name="visibility"/></button>
      {row.status==='deleted'?(
        <button type="button" className="admin-icon-btn" disabled aria-label={t('Nội dung đã bị xóa','Content is deleted')} title={t('Nội dung đã bị xóa','Content is deleted')}><Icon name="visibility_off"/></button>
      ):row.status==='hidden'?(
        <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Hiển thị lại','Restore visibility')} title={t('Hiển thị lại','Restore visibility')} onClick={()=>confirm(row,{status:resource==='posts'?'published':'visible'},t('Hiển thị lại nội dung này?','Show this content again?'))}><Icon name="visibility"/></button>
      ):(
        <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Ẩn nội dung','Hide content')} title={t('Ẩn nội dung','Hide content')} onClick={()=>{setError('');setEdit({type:'moderate',row,targetResource:resource,action:'hidden',reason:'',label:t('Ẩn nội dung','Hide content')})}}><Icon name="visibility_off"/></button>
      )}
      {row.status==='deleted'?(
        <button type="button" className="admin-icon-btn text-error" disabled aria-label={t('Nội dung đã bị xóa','Content is deleted')} title={t('Nội dung đã bị xóa','Content is deleted')}><Icon name="delete"/></button>
      ):(
        <button type="button" className="admin-icon-btn text-error" disabled={busy} aria-label={t('Xóa nội dung','Delete content')} title={t('Xóa nội dung','Delete content')} onClick={()=>{setError('');setEdit({type:'moderate',row,targetResource:resource,action:'deleted',reason:'',label:t('Xóa nội dung','Delete content')})}}><Icon name="delete"/></button>
      )}
      {row.status==='hidden'||row.status==='deleted'?(
        <button type="button" className="admin-icon-btn is-disabled" disabled aria-label={t('Không thể mở nội dung đã ẩn hoặc đã xóa','Cannot open hidden or deleted content')} title={t('Không thể mở nội dung đã ẩn hoặc đã xóa','Cannot open hidden or deleted content')}><Icon name="open_in_new"/></button>
      ):(
        <a href={'/#post-'+(row.post_id||row.id)} target="_blank" rel="noopener noreferrer" className="admin-icon-btn" aria-label={t('Mở bài viết trên trang cộng đồng','Open post in community')} title={t('Mở bài viết trên trang cộng đồng','Open post in community')}><Icon name="open_in_new"/></a>
      )}
    </div>}
    {resource==='categories'&&<button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'category',row,name:row.name,status:row.status})}}>{t('Chỉnh sửa','Edit')}</button>}
    {resource==='contacts'&&<button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'contact',row,status:row.status})}}>{t('Xem và xử lý','View and update')}</button>}
    {resource==='announcements'&&<>
      {row.status==='draft'&&<>
        <button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'announcement',row,title:row.title,body:row.body,mode:'compose'})}}>{t('Sửa','Edit')}</button>
        <button type="button" disabled={busy} className="workspace-primary" onClick={()=>confirm(row,{},t('Phát thông báo này tới tất cả thành viên đang hoạt động?','Broadcast this announcement to all active members?'),'/admin/announcements/'+row.id+'/publish','POST')}>{t('Phát ngay','Publish')}</button>
        <button type="button" disabled={busy} className="text-error" onClick={()=>confirm(row,{},t('Xóa bản nháp này?','Delete this draft?'),'/admin/announcements/'+row.id,'DELETE')}>{t('Xóa','Delete')}</button>
      </>}
      {row.status==='published'&&<>
        <button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'announcement',row:null,title:`[${t('Đính chính','Correction')}] ${row.title}`,body:row.body,mode:'compose'})}}>{t('Đính chính','Rectify')}</button>
        <button type="button" disabled={busy} className="text-error" onClick={()=>confirm(row,{},t('Thu hồi thông báo này? Người dùng sẽ không thấy thông báo này nữa.','Withdraw this announcement? Users will no longer see it as active.'),'/admin/announcements/'+row.id+'/withdraw','POST')}>{t('Thu hồi','Withdraw')}</button>
      </>}
      {row.status==='withdrawn'&&<span className="workspace-meta">{t('Đã thu hồi','Withdrawn')}</span>}
    </>}
   </div></article>)}</div>}
   {data&&<nav className="workspace-pagination" aria-label={t('Phân trang quản trị','Admin pagination')}><button type="button" disabled={loading||page<=1} onClick={()=>setPage(n=>n-1)}>{t('Trước','Previous')}</button><span>{page} / {Math.max(1,data.pagination.total_pages)} · {data.pagination.total} {t('mục','records')}</span><button type="button" disabled={loading||page>=data.pagination.total_pages} onClick={()=>setPage(n=>n+1)}>{t('Sau','Next')}</button></nav>}
  </section>
  </div>
  <dialog ref={dialog} className="workspace-dialog" aria-labelledby="admin-dialog-title" onCancel={e=>{if(busy)e.preventDefault();else {setEdit(null);setHoldingPreview(false);}}} onClose={()=>{setEdit(null);setHoldingPreview(false);}}>{edit&&<form onSubmit={save}><div className="workspace-panel-heading"><h2 id="admin-dialog-title">{edit.type==='content-preview'?(edit.targetResource==='posts'?t('Chi tiết bài viết','Post details'):t('Chi tiết bình luận','Comment details')):edit.type==='announcement'?t('Soạn thông báo hệ thống','Compose announcement'):edit.type==='roles'?t('Sửa vai trò','Edit roles'):edit.type==='category'?t('Danh mục','Category'):edit.type==='contact'?t('Chi tiết & Xử lý liên hệ','Contact details & processing'):edit.label}</h2><button type="button" aria-label={t('Đóng','Close')} disabled={busy} onClick={()=>{setEdit(null);setHoldingPreview(false);}}>×</button></div>
   {edit.type==='content-preview'&&<div className="admin-content-preview">
      <div className="admin-content-preview-header">
        <div className="admin-content-preview-meta">
          <span className="admin-content-preview-author">@{edit.row?.author?.username||edit.row?.author_id}</span>
          <span className="admin-content-preview-time">{stamp(edit.row?.created_at)}</span>
        </div>
        <span className="workspace-badge" data-status={edit.row?.status}>{status(edit.row?.status)}</span>
      </div>
      {edit.targetResource==='posts'&&edit.row?.title&&<h3 className="admin-content-preview-title">{edit.row.title}</h3>}
      {edit.targetResource==='comments'&&edit.row?.post_id&&<div className="admin-content-ref-quote"><Icon name="format_quote"/><span>{t('Bình luận trên bài viết #','Comment on post #')}{edit.row.post_id}</span></div>}
      <div className="admin-content-preview-body" translate="no">{edit.row?.content??edit.row?.body}</div>
      {edit.targetResource==='posts'&&edit.row?.media_url&&edit.row?.status!=='deleted'&&<div className="admin-content-preview-media"><img src={edit.row.media_url.startsWith('http')||edit.row.media_url.startsWith('/')?edit.row.media_url:('/api/v1/admin/posts/'+edit.row.id+'/media')} alt={edit.row.title||'Post media'} loading="lazy"/></div>}
    </div>}
    {edit.type==='confirm'&&<><p className="admin-confirm-target">{edit.row?.display_name||edit.row?.title||edit.row?.body}</p><p>{edit.label||t('Xác nhận thao tác này?','Confirm this action?')}</p></>}
   {edit.type==='announcement'&&<>
     <label>{t('Tiêu đề thông báo','Announcement title')}<input value={edit.title} maxLength={150} required disabled={busy} placeholder={t('Tiêu đề thông báo…','Announcement title…')} onChange={e=>setEdit({...edit,title:e.target.value})}/></label>
     <div className="admin-composer-textarea-header">
       <label htmlFor="admin-announcement-body">{t('Nội dung','Content')}</label>
       <button
         type="button"
         id="admin-preview-eye-btn"
         className={`admin-preview-eye-btn${holdingPreview ? ' is-active' : ''}`}
         aria-label={t('Giữ để xem trước', 'Hold to preview')}
         title={t('Giữ để xem trước', 'Hold to preview')}
         onPointerDown={()=>setHoldingPreview(true)}
         onPointerUp={()=>setHoldingPreview(false)}
         onPointerLeave={()=>setHoldingPreview(false)}
         onPointerCancel={()=>setHoldingPreview(false)}
         onKeyDown={e=>{if(e.key===' '||e.key==='Enter'){e.preventDefault();setHoldingPreview(true);}}}
         onKeyUp={e=>{if(e.key===' '||e.key==='Enter'){e.preventDefault();setHoldingPreview(false);}}}
         onBlur={()=>setHoldingPreview(false)}
       >
         <Icon name="visibility" />
         <span>{t('Giữ để xem trước', 'Hold to preview')}</span>
       </button>
     </div>
     <textarea id="admin-announcement-body" value={edit.body} maxLength={2000} required disabled={busy} rows={6} placeholder={t('Nội dung thông báo toàn hệ thống…','Broadcast announcement body…')} onChange={e=>setEdit({...edit,body:e.target.value})}/>
     <p className="workspace-meta">{t('Thông báo sẽ được gửi tới tất cả thành viên đang hoạt động khi phát.','Announcement will be delivered to all active members when broadcasted.')}</p>
     {holdingPreview&&(
       <div className="admin-hold-preview-overlay" role="region" aria-live="polite">
         <div className="admin-hold-preview-card">
           <div className="admin-hold-preview-badge">
             <Icon name="campaign" />
             <span>AuraMeme System · {t('Xem trước trực tiếp', 'Live preview')}</span>
           </div>
           <h4 className="admin-hold-preview-title">{edit.title?.trim()||t('(Chưa có tiêu đề)','(No title)')}</h4>
           <p className="admin-hold-preview-body">{edit.body?.trim()||t('(Chưa có nội dung)','(No content)')}</p>
           <span className="admin-hold-preview-meta">{t('Thả chuột hoặc phím để tiếp tục soạn thảo', 'Release to resume composing')}</span>
         </div>
       </div>
     )}
   </>}
   {edit.type==='roles'&&<><p>@{edit.row.username}</p><fieldset><legend>{t('Vai trò từ DB','Database roles')}</legend>{['USER','ADMIN'].map(value=><label className="workspace-checkbox" key={value}><input type="checkbox" checked={edit.roles.includes(value)} disabled={busy} onChange={e=>setEdit({...edit,roles:e.target.checked?[...edit.roles,value]:edit.roles.filter(r=>r!==value)})}/>{value}</label>)}</fieldset><p className="workspace-meta">{t('Thay đổi vai trò sẽ kết thúc các phiên của tài khoản đó.','Changing roles ends that account’s sessions.')}</p></>}
   {edit.type==='category'&&<><label>{t('Tên danh mục','Category name')}<input value={edit.name} maxLength={80} required disabled={busy} onChange={e=>setEdit({...edit,name:e.target.value})}/></label>{!edit.row?<label>Slug<input value={edit.slug} maxLength={80} pattern="[a-z0-9-]+" required disabled={busy} onChange={e=>setEdit({...edit,slug:e.target.value})}/></label>:<label>{t('Trạng thái','Status')}<select value={edit.status} disabled={busy} onChange={e=>setEdit({...edit,status:e.target.value})}>{states.categories.map(v=><option value={v} key={v}>{status(v)}</option>)}</select></label>}</>}
   {edit.type==='contact'&&<div className="admin-contact-detail">
      <div className="admin-contact-info-card">
        <div className="admin-contact-info-header">
          <div className="admin-contact-sender">
            <span className="admin-contact-avatar-icon"><Icon name="person" /></span>
            <div>
              <strong className="admin-contact-sender-name">{edit.row.name}</strong>
              <span className="admin-contact-time">{stamp(edit.row.created_at)}</span>
            </div>
          </div>
          <span className="workspace-badge" data-status={edit.row.status}>{status(edit.row.status)}</span>
        </div>
        <h3 className="admin-contact-subject">{edit.row.subject}</h3>
      </div>
      <div className="admin-contact-body-section">
        <label className="admin-contact-section-label">{t('Nội dung tin nhắn', 'Message content')}</label>
        <div className="admin-contact-body-box" translate="no">{edit.row.body}</div>
      </div>
      <div className="admin-contact-status-section">
        <label htmlFor="admin-contact-status-select">{t('Cập nhật trạng thái xử lý', 'Update processing status')}</label>
        <select id="admin-contact-status-select" value={edit.status} disabled={busy} onChange={e=>setEdit({...edit,status:e.target.value})}>
          {states.contacts.map(v=><option value={v} key={v}>{status(v)}</option>)}
        </select>
        <p className="workspace-meta">{t('Chuyển sang "Đang xử lý" hoặc "Đã xử lý" để đồng bộ với đội ngũ hỗ trợ.', 'Set to "In review" or "Resolved" to coordinate with support.')}</p>
      </div>
    </div>}
    {edit.type==='moderate'&&<><p className="admin-confirm-target" translate="no">{edit.row?.title||edit.row?.body||edit.row?.id}</p><p>{edit.action==='hidden'?t('Ẩn nội dung này khỏi cộng đồng?','Hide this content from the community?'):t('Xóa hoàn toàn nội dung này?','Permanently delete this content?')}</p><label>{t('Lý do kiểm duyệt (5-500 ký tự) *','Moderation reason (5-500 chars) *')}<textarea value={edit.reason||''} maxLength={500} required disabled={busy} rows={3} placeholder={t('Nhập lý do gửi thông báo tới tác giả…','Enter reason to notify author…')} onChange={e=>setEdit({...edit,reason:e.target.value})}/></label><p className="workspace-meta">{t('Lý do sẽ được ghi vào nhật ký và gửi thông báo tới tác giả.','Reason will be logged and dispatched to the author.')}</p></>}
   {error&&<p className="workspace-error" role="alert">{error}</p>}
   <div className="workspace-dialog-actions">
      {edit.type==='content-preview'?(
        <button type="button" className="workspace-primary" onClick={()=>{setEdit(null);setHoldingPreview(false);}}>{t('Đóng','Close')}</button>
      ):(
        <>
          <button type="button" disabled={busy} onClick={()=>{setEdit(null);setHoldingPreview(false);}}>{t('Hủy','Cancel')}</button>
          {edit.type==='announcement'?(
            <>
              <button type="button" disabled={busy||!edit.title.trim()||!edit.body.trim()} onClick={e=>{edit.draft=true;save(e);}}>{t('Lưu bản nháp','Save draft')}</button>
              <button type="submit" className="workspace-primary" disabled={busy||!edit.title.trim()||!edit.body.trim()}>{busy?t('Đang phát…','Broadcasting…'):t('Phát thông báo','Broadcast')}</button>
            </>
          ):(
            <button type="submit" className="workspace-primary" disabled={busy}>{busy?t('Đang lưu…','Saving…'):edit.type==='contact'?t('Lưu trạng thái','Save status'):t('Xác nhận','Confirm')}</button>
          )}
        </>
      )}
    </div>
  </form>}</dialog>
 </div></main>;
}
