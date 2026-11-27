import React,{useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {auth,MOCK_AUTH} from '../auth.js';
import {authMessage} from '../auth-client.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {adminPage,adminPresence,canAdmin} from '../admin-api.js';
import {mountBackground} from '../background-effects.js';
import ErrorPage from './ErrorPage.jsx';
import '../workspace.css';

function BackgroundPreviewStage({effectKey,t}){
 const containerRef=useRef(null);
 useEffect(()=>{
  if(!containerRef.current)return;
  const cleanup=mountBackground(containerRef.current,effectKey);
  return()=>{if(typeof cleanup==='function')cleanup();};
 },[effectKey]);
 return (
  <div ref={containerRef} className="admin-bg-preview-canvas-box" data-effect={effectKey||'violet-base'}>
   <canvas className="admin-bg-preview-canvas"/>
  </div>
 );
}

const sections=[['overview','Tổng quan','Overview',['overview']],['users','Người dùng','Users',['users']],['content','Nội dung','Content',['posts','comments','categories']],['contacts','Liên hệ','Contacts',['contacts']],['moderation','Kiểm duyệt','Moderation',['audit-logs','assets','orders']],['notifications','Thông báo','Notifications',['announcements']]];
const labels={overview:['Tổng quan trực tuyến','Live Overview'],users:['Người dùng','Users'],posts:['Bài viết','Posts'],comments:['Bình luận','Comments'],categories:['Danh mục','Categories'],contacts:['Hộp thư liên hệ','Contact inbox'],'audit-logs':['Nhật ký quản trị','Admin activity'],assets:['Trạng thái vật phẩm','Asset status'],orders:['Giao dịch','Transactions'],announcements:['Thông báo hệ thống','System announcements']};
const sectionIcons={overview:'monitoring',users:'group',content:'article',contacts:'inbox',moderation:'shield',notifications:'campaign'};
const resourceNotes={overview:['Theo dõi số thành viên và khách đang hoạt động trong cửa sổ 90 giây gần nhất (tự động làm mới mỗi 15 giây).','Monitor active members and guests within the last 90-second window (auto-refreshes every 15 seconds).'],users:['Quản lý trạng thái và quyền truy cập của thành viên.','Manage member status and access.'],posts:['Xem nội dung và kiểm soát những bài xuất hiện trong cộng đồng.','Review posts and control their visibility in the community.'],comments:['Xem và xử lý bình luận, kể cả nội dung đã ẩn.','Review comments, including hidden content.'],categories:['Sắp xếp nội dung bằng các danh mục dùng chung.','Organize community content with shared categories.'],contacts:['Đọc và phân loại tin nhắn gửi đến AuraMeme.','Read and triage messages sent to AuraMeme.'],'audit-logs':['Ghi lại các thay đổi do quản trị viên thực hiện: ai đã làm gì và khi nào.','Log of administrative actions: who did what and when.'],assets:['Kiểm tra trạng thái hoạt động, tải lên Meme mới và duyệt danh mục vật phẩm.','Inspect catalog availability, upload new Memes, and review pending assets.'],orders:['Xem danh sách và lịch sử các giao dịch thanh toán gói hội viên.','View member subscription orders and payment history.'],announcements:['Soạn thảo, quản lý và phát thông báo tới các thành viên.','Draft, manage, and broadcast announcements to community members.']};
const Icon=({name,...props})=><span className="material-symbols-outlined" aria-hidden="true" {...props}>{name}</span>;
const states={users:['active','locked','deleted'],posts:['draft','published','hidden','deleted'],comments:['visible','hidden','deleted'],categories:['active','hidden'],contacts:['new','in_review','resolved'],assets:['pending','approved','rejected','unknown'],orders:['pending','success','failed','cancelled','expired'],announcements:['draft','published','withdrawn']};
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
  'user.update':['Cập nhật trạng thái người dùng','Updated user status'],
  'user.lock':['Khóa tài khoản người dùng','Locked user account'],
  'user.unlock':['Mở khóa tài khoản người dùng','Unlocked user account'],
  'user.delete':['Xóa tài khoản người dùng (lưu trữ 30 ngày)','Soft-deleted user account (30-day retention)'],
  'user.restore':['Khôi phục tài khoản người dùng','Restored user account'],
  'user.roles':['Cập nhật vai trò người dùng','Updated user roles'],
  'category.create':['Tạo danh mục','Created category'],
  'category.update':['Cập nhật danh mục','Updated category'],
  'asset.review':['Kiểm duyệt vật phẩm','Reviewed asset'],
  'asset.upload':['Tải lên vật phẩm Meme mới (chờ duyệt)','Uploaded new Meme asset (pending review)'],
  'asset.update':['Cập nhật thông tin vật phẩm','Updated asset metadata'],
  'asset.approve':['Duyệt vật phẩm vào Bảo Khố','Approved asset into Vault'],
  'asset.reject':['Từ chối vật phẩm','Rejected asset'],
  'asset.archive':['Ngừng lưu hành vật phẩm','Archived / deactivated asset'],
  'asset.restore':['Khôi phục vật phẩm vào lưu hành','Restored asset to active catalog'],
  'asset.delete':['Xóa vật phẩm chờ duyệt','Removed pending asset']
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
const statusLabels={active:['Hoạt động','Active'],locked:['Đã khóa','Locked'],deleted:['Đã xóa','Deleted'],draft:['Bản nháp','Draft'],published:['Công khai','Published'],visible:['Hiển thị','Visible'],hidden:['Đã ẩn','Hidden'],new:['Mới','New'],in_review:['Đang xử lý','In review'],resolved:['Đã xử lý','Resolved'],pending:['Chờ duyệt','Pending'],approved:['Đã duyệt','Approved'],rejected:['Từ chối','Rejected'],unknown:['Chưa rõ','Unknown'],withdrawn:['Đã thu hồi','Withdrawn'],success:['Thành công','Completed'],failed:['Thất bại','Failed'],cancelled:['Đã hủy','Cancelled'],expired:['Hết hạn','Expired']};
const kindLabels={avatar:['Avatar','Avatar'],background:['Background','Background'],frame:['Khung','Frame'],icon:['Biểu tượng','Icon'],effect:['Hiệu ứng','Effect']};

export default function AdminPage(){
 const session=useSyncExternalStore(auth.subscribe,auth.snapshot),{language}=usePreferences(),t=(vi,en)=>language==='en'?en:vi;
 const title=resource=>t(...labels[resource]),status=value=>resource==='orders'&&value==='pending'?t('Chờ thanh toán','Pending'):statusLabels[value]?t(...statusLabels[value]):value,formatAuditAction=a=>auditActionLabels[a]?t(...auditActionLabels[a]):a,formatAuditTarget=trg=>auditTargetLabels[trg]?t(...auditTargetLabels[trg]):trg,formatKind=k=>kindLabels[k]?t(...kindLabels[k]):k;
 const allowed=!MOCK_AUTH&&session.status==='authenticated'&&canAdmin(session.user),owner=allowed?session.user.id:null;
 const [resource,setResource]=useState('users'),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[filter,setFilter]=useState(''),[role,setRole]=useState(''),[assetKind,setAssetKind]=useState(''),[assetRarity,setAssetRarity]=useState(''),[page,setPage]=useState(1),[revision,setRevision]=useState(0);
 const [result,setData]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState(''),[success,setSuccess]=useState(''),[denied,setDenied]=useState(false),[edit,setEdit]=useState(null),[busy,setBusy]=useState(false),[holdingPreview,setHoldingPreview]=useState(false),[copiedId,setCopiedId]=useState(null),[previewTab,setPreviewTab]=useState('avatar'),[presence,setPresence]=useState(null),[presenceStale,setPresenceStale]=useState(false),[presenceCooldownUntil,setPresenceCooldownUntil]=useState(0);
 const dialog=useRef(null),inflight=useRef(false),currentOwner=useRef(owner),presenceRef=useRef(null);currentOwner.current=owner;presenceRef.current=presence;
 // Never render a previous resource or account while the next read is pending.
 const data=result?.resource===resource&&result.owner===owner?result:null;
 const overviewData=presence?.owner===owner?presence:null;
 const section=sections.find(row=>row[3].includes(resource));
 const explain=e=>(e.code==='RESTORE_WINDOW_EXPIRED'?t('Đã quá thời hạn 30 ngày khôi phục tài khoản.','The 30-day account restoration window has expired.'):e.status===409&&resource==='users'?t('Thay đổi bị từ chối. Phải giữ ít nhất một Admin đang hoạt động.','Change refused. At least one active Admin must remain.'):e.serverMessage||(e.status===409&&resource==='assets'&&e.code!=='DUPLICATE_IMAGE_HASH'?t('Không thể xóa hoặc sửa vật phẩm hệ thống gốc được bảo vệ.','Protected original system assets cannot be modified or deleted.'):authMessage(e,language)));
 useEffect(()=>{setDenied(false);setData(null);setPresence(null);setPresenceStale(false);setPresenceCooldownUntil(0);setEdit(null);setHoldingPreview(false);setError('');setSuccess('');},[owner]);
 useEffect(()=>{
  setData(null);setError('');if(!allowed||denied)return;
  if(resource==='overview'){
   let active=true,timerId=null,inFlight=false;const requestOwner=owner;
   const fetchPresence=async(isManual=false)=>{
    if(!active||inFlight)return;
    if(!isManual&&typeof document!=='undefined'&&document.visibilityState==='hidden')return;
    if(!isManual&&Date.now()<presenceCooldownUntil)return;
    inFlight=true;
    if(!presenceRef.current||presenceRef.current.owner!==owner)setLoading(true);
    try{
     const raw=await auth.read('/admin/presence');
     const parsed=adminPresence(raw);
     if(active&&currentOwner.current===requestOwner){setPresence({...parsed,owner,fetchedAt:Date.now()});setPresenceStale(false);setError('');}
    }catch(e){
     if(!active||currentOwner.current!==requestOwner)return;
     if(e.status===403){setPresence(null);setDenied(true);auth.refresh().catch(()=>{});return;}
     if(e.status===401){setPresence(null);auth.refresh().catch(()=>{});return;}
     if(e.status===429){const sec=Number.isFinite(e.retryAfter)&&e.retryAfter>0?e.retryAfter:60;setPresenceCooldownUntil(Date.now()+sec*1000);}
     if(presenceRef.current&&presenceRef.current.owner===owner){setPresenceStale(true);}
     setError(explain(e));
    }finally{inFlight=false;if(active)setLoading(false);}
   };
   const startPoll=()=>{if(timerId===null&&active)timerId=setInterval(()=>fetchPresence(false),15000);};
   const stopPoll=()=>{if(timerId!==null){clearInterval(timerId);timerId=null;}};
   const onVis=()=>{if(!active)return;if(document.visibilityState==='visible'){fetchPresence(false);startPoll();}else{stopPoll();}};
   fetchPresence(true);
   if(typeof document==='undefined'||document.visibilityState!=='hidden')startPoll();
   const staleCheck=setInterval(()=>{if(active&&presenceRef.current?.owner===owner&&Date.now()-presenceRef.current.fetchedAt>45000)setPresenceStale(true);},15000);
   if(typeof document!=='undefined')document.addEventListener('visibilitychange',onVis);
   return()=>{active=false;stopPoll();clearInterval(staleCheck);if(typeof document!=='undefined')document.removeEventListener('visibilitychange',onVis);};
  }
  let active=true;setLoading(true);
  const params=new URLSearchParams({page:String(page),page_size:'10'});if(search)params.set('search',search);if(filter)params.set(resource==='assets'?'review_status':'status',filter);if(resource==='users'&&role)params.set('role',role);if(resource==='assets'&&assetKind)params.set('kind',assetKind);if(resource==='assets'&&assetRarity)params.set('rarity',assetRarity);
  auth.read('/admin/'+resource+'?'+params).then(value=>adminPage(value,resource)).then(value=>{if(active){if(value.items.length===0&&page>1&&value.pagination.total>0){setPage(p=>Math.max(1,p-1));return;}setData({...value,resource,owner});}}).catch(e=>{if(active){setError(explain(e));if(e.status===403){setDenied(true);auth.refresh().catch(()=>{})}if(e.status===401)auth.refresh().catch(()=>{});}}).finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[allowed,denied,owner,resource,search,filter,role,assetKind,assetRarity,page,revision]);
 useEffect(()=>{if(edit&&!dialog.current?.open)dialog.current.showModal();else if(!edit){dialog.current?.close();setHoldingPreview(false);}},[edit]);
 function choose(value){setResource(value);setPage(1);setQuery('');setSearch('');setFilter('');setRole('');setAssetKind('');setAssetRarity('');setError('');setSuccess('');}
 function confirm(row,body,label,path='/admin/'+resource+'/'+row.id,method='PATCH'){setError('');setEdit({type:'confirm',row,body,label,path,method})}
 async function save(event){
  event.preventDefault();if(edit?.type==='content-preview'||edit?.type==='announcement-preview'||edit?.type==='receipt-preview'||(edit?.type==='asset-preview'&&!edit.pendingAction)){setEdit(null);return;}if(inflight.current||!edit)return;inflight.current=true;setBusy(true);setError('');setSuccess('');const requestOwner=owner;
  let method=edit.method||'PATCH',path=edit.path||'/admin/'+resource+'/'+(edit.row?.id||''),body=edit.body;
  if(edit.type==='roles'){method='PUT';path='/admin/users/'+edit.row.id+'/roles';body={roles:edit.roles}}
  if(edit.type==='category'){method=edit.row?'PATCH':'POST';path='/admin/categories'+(edit.row?'/'+edit.row.id:'');body=edit.row?{name:edit.name,status:edit.status}:{name:edit.name,slug:edit.slug};}
  if(edit.type==='contact'){path='/admin/contacts/'+edit.row.id;body={status:edit.status}}
  if(edit.type==='asset-edit'){
    method='PATCH';path='/admin/assets/'+edit.row.id;
    body={display_name:(edit.display_name||'').trim(),rarity:edit.rarity};
  }
  if(edit.type==='asset-preview'&&edit.pendingAction){
    method='PATCH';path='/admin/assets/'+edit.row.id;
    body={action:edit.pendingAction};
  }
  if(edit.type==='asset-upload'){
    if(!edit.file){
      setError(t('Vui lòng chọn file ảnh (.jpg, .png) hoặc gói .zip.','Please select an image (.jpg, .png) or .zip archive.'));
      inflight.current=false;setBusy(false);return;
    }
    method='POST';path='/admin/assets/upload';
    const fd=new FormData();fd.append('file',edit.file);
    body=fd;
  }
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
  try{const res=await auth.write(method,path,body);if(currentOwner.current!==requestOwner)return;setEdit(null);if((edit.action==='deleted'||method==='DELETE')&&data?.items?.length===1&&page>1){setPage(p=>Math.max(1,p-1));}setRevision(n=>n+1);setSuccess(edit.type==='asset-upload'?t(`Đã tải lên ${res?.uploaded_count||1} vật phẩm Meme vào hàng chờ duyệt (Pending).`,`Uploaded ${res?.uploaded_count||1} Meme asset(s) to the Pending queue.`):t('Đã lưu thay đổi.','Changes saved.'));if(resource==='users'&&edit.row?.id===requestOwner)await auth.refresh().catch(()=>{});}
  catch(e){if(currentOwner.current===requestOwner){if(edit.type==='asset-preview')edit.pendingAction=null;setError(explain(e));if(e.status===403){setData(null);setDenied(true);setEdit(null);auth.refresh().catch(()=>{})}}}
  finally{inflight.current=false;setBusy(false)}
 }
 const copyTargetId=id=>{if(navigator?.clipboard?.writeText){navigator.clipboard.writeText(id).then(()=>{setCopiedId(id);setTimeout(()=>setCopiedId(null),2000)}).catch(()=>{})}};
 const stamp=value=>new Date(value).toLocaleString(language==='en'?'en-GB':'vi-VN');
 const restoreDaysLeft=row=>{if(row?.status!=='deleted')return null;if(!row.deleted_at)return 30;const elapsed=(Date.now()-Date.parse(row.deleted_at))/86400000;return Math.max(0,Math.ceil(30-elapsed));};
 if(!allowed||denied)return <ErrorPage status={404} />;
 return <main className="workspace-page admin-page"><div className="workspace-content admin-layout">
  <aside className="admin-sidebar">
   <div className="admin-workspace-brand"><span className="admin-brand-mark"><img src="/assets/brand/04_admin_guardian-circle-48.png" alt="AuraMeme Guardian" width="40" height="40" className="admin-brand-logo-img"/></span><div><strong>AuraMeme</strong><span>Workspace</span></div></div>
   <nav className="workspace-tabs" aria-label={t('Khu quản trị','Admin sections')}>{sections.map(([id,vi,en,resources])=><button type="button" key={id} aria-current={section[0]===id?'page':undefined} onClick={()=>choose(resources[0])}><Icon name={sectionIcons[id]}/><span>{t(vi,en)}</span><Icon name="chevron_right" className="material-symbols-outlined admin-nav-arrow"/></button>)}</nav>
   <div className="admin-sidebar-bottom"><a className="admin-home-link" href="/"><Icon name="arrow_back"/><span>{t('Về Trang chủ','Back to Home')}</span></a></div>
  </aside>
  <div className="admin-main">
  <header className="admin-heading"><div><p className="admin-breadcrumb">Workspace <Icon name="chevron_right"/>{t(section[1],section[2])}</p><h1>{t('Không gian quản trị','Admin Workspace')}</h1></div></header>
  {section[3].length>1&&<nav className="workspace-subtabs" aria-label={t('Chức năng quản trị','Admin tools')}>{section[3].map(value=><button type="button" key={value} aria-pressed={resource===value} onClick={()=>choose(value)}>{title(value)}</button>)}</nav>}
  <section className="workspace-panel admin-list-panel" aria-labelledby="admin-list-title" data-resource={resource}><div className="workspace-panel-heading"><div><div className="admin-list-title"><h2 id="admin-list-title">{title(resource)}</h2>{data&&<span className="admin-count" aria-label={t('Tổng số mục','Total records')}>{data.pagination.total}</span>}</div><p className="admin-list-note">{t(...resourceNotes[resource])}</p></div><div className="admin-toolbar-actions"><button type="button" className="admin-refresh" disabled={loading||busy} aria-label={t('Tải lại danh sách','Refresh list')} onClick={()=>setRevision(n=>n+1)}><Icon name="refresh"/></button>{resource==='assets'&&assetKind!=='background'&&<button type="button" className="admin-icon-btn workspace-primary admin-add-asset-btn" disabled={loading||busy} aria-label={t('Thêm vật phẩm','Add asset')} title={t('Thêm vật phẩm','Add asset')} onClick={()=>{setError('');setEdit({type:'asset-upload',file:null})}}><Icon name="add"/></button>}{resource==='announcements'&&<button type="button" className="workspace-primary admin-broadcast-btn" disabled={loading||busy} onClick={()=>{setError('');setEdit({type:'announcement',row:null,title:'',body:'',mode:'compose'})}}><Icon name="campaign"/>{t('Phát thông báo','Broadcast')}</button>}{resource==='categories'&&<button type="button" className="workspace-primary admin-icon-btn admin-add-asset-btn" aria-label={t('Thêm danh mục','Add category')} title={t('Thêm danh mục','Add category')} onClick={()=>{setError('');setEdit({type:'category',row:null,name:'',slug:''})}}><Icon name="add"/></button>}</div></div>
   {resource==='overview'?(
    <>
     {error&&!edit&&<div className="workspace-error" role="alert">{error}<button type="button" onClick={()=>setRevision(n=>n+1)}>{t('Thử lại','Retry')}</button></div>}
     {presenceStale&&overviewData&&<p className="admin-presence-stale" role="status">{t('Dữ liệu có thể đã cũ hơn 45 giây. Đang chờ lần làm mới tiếp theo.','Data may be stale (>45s). Waiting for next refresh.')}</p>}
     {loading&&!overviewData?(
      <div className="admin-loading" role="status" aria-busy="true"><span className="workspace-sr">{t('Đang tải…','Loading…')}</span>{[0,1,2].map(n=><div className="admin-skeleton-row" key={n} aria-hidden="true"><span/><div><i/><i/></div><b/></div>)}</div>
     ):overviewData?(
      <div className="admin-presence-wrap" aria-live="polite">
       <div className="admin-presence-grid">
        <article className="admin-presence-card is-total">
         <span className="admin-presence-label"><Icon name="groups"/>{t('Tổng số đang hoạt động','Total active')}</span>
         <strong className="admin-presence-value" data-testid="presence-total">{overviewData.active_total}</strong>
        </article>
        <article className="admin-presence-card">
         <span className="admin-presence-label"><Icon name="verified_user"/>{t('Thành viên đang hoạt động','Active members')}</span>
         <strong className="admin-presence-value" data-testid="presence-users">{overviewData.active_users}</strong>
        </article>
        <article className="admin-presence-card">
         <span className="admin-presence-label"><Icon name="person_outline"/>{t('Khách đang hoạt động','Active guests')}</span>
         <strong className="admin-presence-value" data-testid="presence-guests">{overviewData.active_guests}</strong>
        </article>
       </div>
       {overviewData.active_total===0&&<div className="admin-empty admin-presence-empty"><Icon name="hourglass_empty"/><h3>{t('Chưa ghi nhận phiên hoạt động trong cửa sổ hiện tại.','No active sessions recorded in the current window.')}</h3></div>}
       <p className="workspace-meta admin-presence-meta">
        <span>{t(`Cửa sổ đo ${overviewData.window_seconds} giây gần nhất`,`Last ${overviewData.window_seconds}-second window`)}</span>
        <span>·</span>
        <span>{t('Cập nhật cuối: ','Last updated: ')}<time dateTime={overviewData.generated_at}>{stamp(overviewData.generated_at)}</time></span>
       </p>
      </div>
     ):!error&&<div className="admin-empty"><Icon name="monitoring"/><h3>{t('Chưa có dữ liệu trực tuyến.','No presence data yet.')}</h3></div>}
    </>
   ):(
   <>
   <form className="workspace-filters" role="search" aria-label={t('Tìm trong khu quản trị','Search Admin Workspace')} onSubmit={e=>{e.preventDefault();setSearch(query.trim());setPage(1)}}><div className="admin-search-field"><label htmlFor="admin-search-input">{t('Tìm kiếm','Search')}</label><div className="admin-search-input-wrap"><input id="admin-search-input" type="search" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} /><button type="submit" className="admin-search-button" aria-label={t('Tìm kiếm','Search')} title={t('Tìm kiếm','Search')}><Icon name="search"/></button></div></div>{states[resource]&&<label>{t('Trạng thái','Status')}<select value={filter} onChange={e=>{setFilter(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option>{states[resource].map(v=><option key={v} value={v}>{status(v)}</option>)}</select></label>}{resource==='assets'&&<><label>{t('Loại','Kind')}<select value={assetKind} onChange={e=>{setAssetKind(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option><option value="avatar">{t('Meme Avatar','Meme Avatar')}</option><option value="background">{t('Background','Background')}</option></select></label><label>{t('Hạng','Rank')}<select value={assetRarity} onChange={e=>{setAssetRarity(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option>{['D','C','B','A','S'].map(r=><option key={r} value={r}>{t(`Hạng ${r}`,`Rank ${r}`)}</option>)}</select></label></>}{resource==='users'&&<label>{t('Vai trò','Role')}<select value={role} onChange={e=>{setRole(e.target.value);setPage(1)}}><option value="">{t('Tất cả','All')}</option><option>USER</option><option>ADMIN</option></select></label>}</form>
   {error&&!edit&&<div className="workspace-error" role="alert">{error}<button type="button" onClick={()=>setRevision(n=>n+1)}>{t('Thử lại','Retry')}</button></div>}{success&&<p role="status" className="workspace-success">{success}</p>}
   <div className="admin-column-head" aria-hidden="true"><span>{resource==='users'?t('Thành viên / Vai trò','Member / Role'):title(resource)}</span><span>{resource==='audit-logs'?t('Thời gian','Time'):t('Trạng thái','Status')}</span><span>{resource==='audit-logs'?'':t('Thao tác','Actions')}</span></div>
   {loading?<div className="admin-loading" role="status" aria-busy="true"><span className="workspace-sr">{t('Đang tải…','Loading…')}</span>{[0,1,2].map(n=><div className="admin-skeleton-row" key={n} aria-hidden="true"><span/><div><i/><i/></div><b/></div>)}</div>:data&&!data.items.length?<div className="admin-empty"><Icon name="search_off"/><h3>{t('Không có dữ liệu phù hợp.','No matching records.')}</h3><p>{t('Thử thay đổi từ khóa hoặc bỏ bộ lọc.','Try a different search or clear the filters.')}</p>{(search||filter||role||assetKind||assetRarity)&&<button type="button" onClick={()=>choose(resource)}>{t('Xóa bộ lọc','Clear filters')}</button>}</div>:<div className="workspace-rows" key={resource}>{data?.items.map(row=><article className="workspace-row" key={row.id} data-admin-id={row.id}><div className="workspace-row-main">
    {resource==='users'&&<div className="admin-identity"><span className="admin-initial" aria-hidden="true">{row.display_name.trim().slice(0,1).toUpperCase()||'@'}</span><div><h3 translate="no">{row.display_name}</h3><p translate="no">@{row.username}</p>{row.email&&<p className="admin-user-email" translate="no">{row.email}</p>}<p className="admin-role-list">{row.roles.length?row.roles.map(value=><span key={value} data-role={value}>{value}</span>):t('Chưa có vai trò','No role')}</p></div></div>}
    {(resource==='posts'||resource==='comments')&&<><h3>{resource==='posts'?row.title:'@'+row.author.username}</h3><p className="workspace-meta">@{row.author.username} · {stamp(row.created_at)}</p><p className="admin-content-snippet" translate="no">{(row.content??row.body)?.length>120?((row.content??row.body).slice(0,120)+'…'):(row.content??row.body)}</p></>}
    {resource==='categories'&&<><h3>{row.name}</h3><p className="workspace-meta">{row.slug}</p></>}
    {resource==='contacts'&&<><h3>{row.subject}</h3><p>{row.name}</p><p className="workspace-meta">{stamp(row.created_at)}</p></>}
    {resource==='assets'&&<div className="admin-asset-row-main">
      <h3 translate="no">{row.display_name||row.slug}</h3>
      <p className="workspace-meta admin-asset-filename">
        <Icon name="image" style={{fontSize:14,verticalAlign:'text-bottom',marginRight:4}}/>
        <code>{row.filename||row.slug}</code>
      </p>
      <p className="workspace-meta admin-asset-id-line">
        <span>{formatKind(row.kind)} · {t(`Hạng ${row.rarity}`,`Rank ${row.rarity}`)} · </span>
        <code>ID: {row.id}</code>
        <button type="button" className="admin-copy-btn" onClick={()=>copyTargetId(row.id)} aria-label={t('Sao chép ID vật phẩm','Copy asset ID')} title={t('Sao chép ID vật phẩm','Copy asset ID')}>
          <Icon name={copiedId===row.id?'check':'content_copy'}/>
        </button>
      </p>
    </div>}
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
    {resource==='announcements'&&<><h3>{row.title}</h3><p className="workspace-meta">@{row.actor_username||'admin'} · {stamp(row.created_at)}{row.published_at&&` · ${t('Phát lúc:','Broadcasted at:')} ${stamp(row.published_at)}`}{typeof row.recipients_count==='number'&&` · ${row.recipients_count} ${t('người nhận','recipients')}`}</p><p className="admin-content-snippet" translate="no">{row.body?.length>120?(row.body.slice(0,120)+'…'):row.body}</p></>}
    {resource==='orders'&&<div>
      <h3 className="flex items-center gap-2">
        <code className="text-secondary font-mono">{row.order_code}</code>
        <span className="workspace-badge" style={{textTransform:'uppercase',fontSize:'11px',background:row.tier==='prime'?'rgba(234, 179, 8, 0.2)':'rgba(56, 189, 248, 0.2)',color:row.tier==='prime'?'#facc15':'#38bdf8'}}>
          {row.tier==='prime'?'Aura Prime':'Aura Plus'}
        </span>
      </h3>
      <p className="workspace-meta">
        <span>{row.owner_username&&('@'+row.owner_username+' · ')}{row.amount_usd_cents!=null&&((row.amount_usd_cents/100).toFixed(2)+' '+row.currency+' · ')}{row.amount_vnd_formatted||(row.amount_vnd?.toLocaleString('vi-VN')+' đ')}</span>
        <span>·</span>
        <span>{row.provider==='paypal_sandbox'?'PayPal':row.provider==='sandbox_simulated'?'Thẻ':(row.provider==='unselected'||!row.provider?t('Chưa chọn','Not selected'):row.provider)}</span>
        <span>·</span>
        <span>{row.created_at?stamp(row.created_at):''}</span>
        {row.completed_at&&<span>· {t('Hoàn tất','Completed')}: {stamp(row.completed_at)}</span>}{row.provider_txn_id&&<span>· Txn: <code className="text-outline">{row.provider_txn_id}</code></span>}
      </p>
    </div>}
   </div><div className="admin-row-status">
    {resource==='audit-logs'&&<time className="workspace-meta" dateTime={row.created_at}>{stamp(row.created_at)}</time>}
    {resource==='orders'&&<span className="workspace-badge" data-status={row.status} style={{fontWeight:600}}>{status(row.status)}</span>}
    {resource==='assets'&&row.review_status&&<span className="workspace-badge" data-status={row.review_status}>{status(row.review_status)}</span>}
    {row.status&&resource!=='orders'&&<span className="workspace-badge" data-status={row.status}>{status(row.status)}</span>}{resource==='users'&&row.status==='deleted'&&(()=>{const days=restoreDaysLeft(row);return <span className="workspace-meta" style={{marginTop:4}}>{days>0?t(`Còn ${days} ngày khôi phục`,`${days} days left to restore`):t('Hết hạn khôi phục','Restore expired')}</span>;})()}{resource==='assets'&&<span className="workspace-badge" data-status={row.active?'active':'hidden'}>{row.active?t('Đang bật','Active'):(row.review_status==='approved'?t('Ngừng lưu hành','Archived'):t('Đang tắt','Inactive'))}</span>}{resource==='assets'&&row.system_protected&&<span className="workspace-badge" data-status="active">{t('Hệ thống gốc','Protected')}</span>}
    </div><div className="workspace-row-actions">{resource==='users'&&<div className="admin-action-icons">{(row.username==='khang_dev'||row.id==='abcfa9f6-c9d2-4181-9b4b-118a4bb6c647')?(
      null
    ):row.status!=='deleted'?(
      <>
        <button type="button" className="admin-icon-btn" disabled={busy||(session.user?.username==='kien_dev'&&row.username==='kien_dev')} aria-label={row.status==='active'?t('Khóa tài khoản','Lock account'):t('Mở khóa tài khoản','Unlock account')} title={row.status==='active'?t('Khóa tài khoản','Lock account'):t('Mở khóa tài khoản','Unlock account')} onClick={()=>confirm(row,{status:row.status==='active'?'locked':'active'},row.status==='active'?t('Khóa tài khoản này?','Lock this account?'):t('Mở khóa tài khoản này?','Unlock this account?'))}><Icon name={row.status==='active'?'lock':'lock_open'}/></button>
        <button type="button" className="admin-icon-btn text-error" disabled={busy||(session.user?.username==='kien_dev'&&row.username==='kien_dev')} aria-label={t('Xóa tài khoản','Delete account')} title={t('Xóa tài khoản (lưu 30 ngày)','Delete account (30-day retention)')} onClick={()=>confirm(row,null,t('Xóa tài khoản này? Tài khoản sẽ bị vô hiệu hóa ngay lập tức và có thể khôi phục trong vòng 30 ngày.','Delete this account? The account will be deactivated immediately and can be restored within 30 days.'),'/admin/users/'+row.id,'DELETE')}><Icon name="delete"/></button>
      </>
    ):(
      (()=>{const days=restoreDaysLeft(row);return <button type="button" className="admin-icon-btn" disabled={busy||days<=0} aria-label={t('Khôi phục tài khoản','Restore account')} title={days>0?t(`Khôi phục tài khoản (còn ${days} ngày)`,`Restore account (${days} days left)`):t('Đã hết hạn 30 ngày khôi phục','30-day restore window expired')} onClick={()=>confirm(row,{},t('Khôi phục tài khoản này về trạng thái hoạt động?','Restore this account to active status?'),'/admin/users/'+row.id+'/restore','POST')}><Icon name="restore_from_trash"/></button>;})()
    )}</div>}
    {resource==='orders'&&<div className="admin-action-icons">
      {row.status==='success'?(
        <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Biên lai thu tiền điện tử','Electronic payment receipt')} title={t('Biên lai thu tiền điện tử','Electronic payment receipt')} onClick={()=>{setError('');setEdit({type:'receipt-preview',row})}}><Icon name="receipt_long"/></button>
      ):(
        <button type="button" className="admin-icon-btn is-disabled" disabled aria-label={t('Chỉ đơn thành công mới có biên lai','Receipt only available for successful orders')} title={t('Chỉ đơn thành công mới có biên lai','Receipt only available for successful orders')}><Icon name="receipt_long"/></button>
      )}
    </div>}
    {resource==='assets'&&<div className="admin-action-icons">
      <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Xem vật phẩm','View asset')} title={t('Xem vật phẩm','View asset')} onClick={()=>{setError('');setPreviewTab('avatar');setEdit({type:'asset-preview',row})}}><Icon name="visibility"/></button>
      <button type="button" className="admin-icon-btn" disabled={busy||row.system_protected} aria-label={t('Sửa vật phẩm','Edit asset')} title={row.system_protected?t('75 vật phẩm gốc của hệ thống được bảo vệ','75 original system assets are protected'):t('Sửa tên hiển thị & hạng','Edit display name & rank')} onClick={()=>{setError('');setEdit({type:'asset-edit',row,display_name:row.display_name||row.slug,rarity:row.rarity})}}><Icon name="edit"/></button>
      {row.system_protected?(
        <button type="button" className="admin-icon-btn is-disabled" disabled aria-label={t('Vật phẩm hệ thống được bảo vệ','Protected system asset')} title={t('75 vật phẩm gốc của hệ thống được bảo vệ','75 original system assets are protected')}><Icon name="shield"/></button>
      ):row.review_status==='pending'?(
        <button type="button" className="admin-icon-btn text-error" disabled={busy} aria-label={t('Từ chối vật phẩm','Reject asset')} title={t('Từ chối vật phẩm chờ duyệt','Reject pending asset')} onClick={()=>confirm(row,{action:'reject'},t('Từ chối vật phẩm chờ duyệt này?','Reject this pending asset?'),'/admin/assets/'+row.id,'PATCH')}><Icon name="block"/></button>
      ):row.active?(
        <button type="button" className="admin-icon-btn text-error" disabled={busy} aria-label={t('Ngừng lưu hành vật phẩm','Archive asset')} title={t('Ngừng lưu hành vật phẩm','Archive / deactivate asset')} onClick={()=>confirm(row,{action:'archive'},t('Ngừng lưu hành vật phẩm này? Vật phẩm sẽ tự tháo khỏi hồ sơ đang trang bị nhưng vẫn giữ nguyên lịch sử sở hữu và mở rương.','Archive this asset? It will be unequipped from profiles while preserving inventory and chest history.'),'/admin/assets/'+row.id,'PATCH')}><Icon name="unpublished"/></button>
      ):(
        <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Khôi phục vật phẩm','Restore asset')} title={t('Khôi phục vật phẩm vào lưu hành','Restore asset to active catalog')} onClick={()=>confirm(row,{action:'approve'},t('Khôi phục vật phẩm này trở lại lưu hành? Không tạo phần thưởng trùng lặp.','Restore this asset to active catalog? No duplicate grants will be created.'),'/admin/assets/'+row.id,'PATCH')}><Icon name="restore_from_trash"/></button>
      )}
    </div>}
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
    {resource==='categories'&&<div className="admin-action-icons"><button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Chỉnh sửa danh mục','Edit category')} title={t('Chỉnh sửa danh mục','Edit category')} onClick={()=>{setError('');setEdit({type:'category',row,name:row.name,status:row.status})}}><Icon name="edit"/></button></div>}
    {resource==='contacts'&&<button type="button" disabled={busy} onClick={()=>{setError('');setEdit({type:'contact',row,status:row.status})}}>{t('Xem và xử lý','View and update')}</button>}
    {resource==='announcements'&&<div className="admin-action-icons">
      <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Xem chi tiết thông báo','View announcement details')} title={t('Xem chi tiết thông báo','View announcement details')} onClick={()=>{setError('');setEdit({type:'announcement-preview',row})}}><Icon name="visibility"/></button>
      {row.status==='draft'&&<>
        <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Sửa bản nháp','Edit draft')} title={t('Sửa bản nháp','Edit draft')} onClick={()=>{setError('');setEdit({type:'announcement',row,title:row.title,body:row.body,mode:'compose'})}}><Icon name="edit"/></button>
        <button type="button" className="admin-icon-btn" disabled={busy} aria-label={t('Phát thông báo ngay','Broadcast announcement now')} title={t('Phát thông báo ngay','Broadcast announcement now')} onClick={()=>confirm(row,{},t('Phát thông báo này tới tất cả thành viên đang hoạt động?','Broadcast this announcement to all active members?'),'/admin/announcements/'+row.id+'/publish','POST')}><Icon name="send"/></button>
        <button type="button" className="admin-icon-btn text-error" disabled={busy} aria-label={t('Xóa bản nháp','Delete draft')} title={t('Xóa bản nháp','Delete draft')} onClick={()=>confirm(row,{},t('Xóa bản nháp này?','Delete this draft?'),'/admin/announcements/'+row.id,'DELETE')}><Icon name="delete"/></button>
      </>}
      {row.status==='published'&&<button type="button" className="admin-icon-btn text-error" disabled={busy} aria-label={t('Thu hồi thông báo','Withdraw announcement')} title={t('Thu hồi thông báo','Withdraw announcement')} onClick={()=>confirm(row,{},t('Thu hồi thông báo này? Người dùng sẽ không thấy thông báo này nữa.','Withdraw this announcement? Users will no longer see it as active.'),'/admin/announcements/'+row.id+'/withdraw','POST')}><Icon name="undo"/></button>}
    </div>}
   </div></article>)}</div>}
   {data&&<nav className="workspace-pagination" aria-label={t('Phân trang quản trị','Admin pagination')}><button type="button" disabled={loading||page<=1} onClick={()=>setPage(n=>n-1)}>{t('Trước','Previous')}</button><span>{(()=>{const fromIndex=data.pagination.total===0?0:(page-1)*data.pagination.page_size+1;const toIndex=Math.min(page*data.pagination.page_size,data.pagination.total);return t(`Tổng cộng: ${data.pagination.total} mục · Đang hiển thị ${fromIndex}–${toIndex} · Trang ${page}/${Math.max(1,data.pagination.total_pages)}`,`Total: ${data.pagination.total} records · Showing ${fromIndex}–${toIndex} · Page ${page}/${Math.max(1,data.pagination.total_pages)}`);})()}</span><button type="button" disabled={loading||page>=data.pagination.total_pages} onClick={()=>setPage(n=>n+1)}>{t('Sau','Next')}</button></nav>}
   </>)}
  </section>
  </div>
  <dialog ref={dialog} className={`workspace-dialog ${edit?.type==='receipt-preview'?'admin-receipt-dialog':''}`} aria-labelledby="admin-dialog-title" onCancel={e=>{if(busy)e.preventDefault();else {setEdit(null);setHoldingPreview(false);}}} onClose={()=>{setEdit(null);setHoldingPreview(false);}}>{edit&&<form onSubmit={save}><div className="workspace-panel-heading"><h2 id="admin-dialog-title">{edit.type==='receipt-preview'?t('Biên lai thu tiền điện tử','Electronic payment receipt'):edit.type==='announcement-preview'?t('Chi tiết thông báo hệ thống','Announcement details'):edit.type==='content-preview'?(edit.targetResource==='posts'?t('Chi tiết bài viết','Post details'):t('Chi tiết bình luận','Comment details')):edit.type==='asset-preview'?t('Chi tiết & Xem trước vật phẩm','Asset details & preview'):edit.type==='asset-edit'?t('Chỉnh sửa vật phẩm','Edit asset'):edit.type==='asset-upload'?t('Thêm Meme vào Bảo Khố','Add Meme to Vault'):edit.type==='announcement'?t('Soạn thông báo hệ thống','Compose system announcement'):edit.type==='roles'?t('Sửa vai trò','Edit roles'):edit.type==='category'?t('Danh mục','Category'):edit.type==='contact'?t('Chi tiết & Xử lý liên hệ','Contact details & processing'):edit.label}</h2><button type="button" aria-label={t('Đóng','Close')} disabled={busy} onClick={()=>{setEdit(null);setHoldingPreview(false);}}>×</button></div>
   {edit.type==='asset-preview'&&<div className="admin-asset-preview-modal">
      <div className="admin-content-preview-header">
        <div className="admin-content-preview-meta">
          <strong className="admin-content-preview-author" translate="no">{edit.row.display_name||edit.row.slug}</strong>
          <code className="admin-content-preview-time">ID: {edit.row.id}</code>
        </div>
        <div style={{display:'flex',gap:6,alignItems:'center'}}>
          <span className="workspace-badge">{formatKind(edit.row.kind)} · {t(`Hạng ${edit.row.rarity}`,`Rank ${edit.row.rarity}`)}</span>
          <span className="workspace-badge" data-status={edit.row.review_status}>{status(edit.row.review_status)}</span>
        </div>
      </div>
      {edit.row.kind==='background'?(
        <BackgroundPreviewStage effectKey={edit.row.effect_key} t={t} />
      ):(
        <>
          <div className="admin-asset-context-tabs" role="tablist">
            {[
              ['avatar',t('Ảnh 1:1','1:1 Image')],
              ['profile',t('Khung Hồ sơ','Profile Frame')],
              ['reaction',t('Thả Meme','Post Reaction')],
              ['chest',t('Rương Bảo Khố','Vault Chest')],
            ].map(([k,lbl])=>(
              <button key={k} type="button" role="tab" aria-selected={previewTab===k} className={previewTab===k?'is-active':''} onClick={()=>setPreviewTab(k)}>{lbl}</button>
            ))}
          </div>
          <div className="admin-asset-context-stage" data-context={previewTab}>
            {previewTab==='avatar'&&(
              <div className="admin-ctx-avatar">
                <img src={`/api/v1/admin/assets/${edit.row.id}/media`} alt={edit.row.display_name||edit.row.slug} width="160" height="160"/>
              </div>
            )}
            {previewTab==='profile'&&(
              <div className="admin-ctx-profile">
                <div className="admin-ctx-profile-ring">
                  <img src={`/api/v1/admin/assets/${edit.row.id}/media`} alt="" width="88" height="88"/>
                </div>
                <div>
                  <strong>{session.user?.display_name||'Tu Tiên Giả'}</strong>
                  <span>@{session.user?.username||'cultivator'} · {t(`Avatar Hạng ${edit.row.rarity}`,`Rank ${edit.row.rarity} Avatar`)}</span>
                </div>
              </div>
            )}
            {previewTab==='reaction'&&(
              <div className="admin-ctx-reaction">
                <p>{t('Mô phỏng hiển thị khi thả Meme trong bài viết / bình luận:','Simulated Meme reaction on a post / comment:')}</p>
                <div className="admin-ctx-reaction-pill">
                  <img src={`/api/v1/admin/assets/${edit.row.id}/media`} alt="" width="36" height="36"/>
                  <span>+1</span>
                </div>
              </div>
            )}
            {previewTab==='chest'&&(
              <div className="admin-ctx-chest" data-rarity={edit.row.rarity}>
                <span className="admin-ctx-chest-rarity">{t(`HẠNG ${edit.row.rarity}`,`RANK ${edit.row.rarity}`)}</span>
                <img src={`/api/v1/admin/assets/${edit.row.id}/media`} alt="" width="112" height="112"/>
                <strong>{edit.row.display_name||edit.row.slug}</strong>
                <small>{t('Xem trước thẻ vật phẩm trong Rương Meme (không cộng EXP)','Simulated Meme Chest card (no EXP awarded)')}</small>
              </div>
            )}
          </div>
        </>
      )}
   </div>}
   {edit.type==='asset-edit'&&<div className="admin-asset-edit-fields">
      <label>
        <span>{t('1. Tên file','1. Filename')}</span>
        <input value={edit.row.filename||edit.row.slug} readOnly disabled className="is-readonly"/>
      </label>
      <label>
        <span>{t('2. ID vật phẩm','2. Asset ID')}</span>
        <input value={edit.row.id} readOnly disabled className="is-readonly"/>
      </label>
      <label>
        <span>{t('3. Tên ảnh','3. Image name')}</span>
        <input value={edit.display_name} maxLength={80} required disabled={busy} onChange={e=>setEdit({...edit,display_name:e.target.value})}/>
      </label>
      <label>
        <span>{t('4. Hạng vật phẩm','4. Asset rank')}</span>
        <select value={edit.rarity} disabled={busy} onChange={e=>setEdit({...edit,rarity:e.target.value})}>
          {['D','C','B','A','S'].map(r=><option key={r} value={r}>{t(`Hạng ${r}`,`Rank ${r}`)}</option>)}
        </select>
      </label>
   </div>}
   {edit.type==='receipt-preview'&&<div className="admin-receipt-preview-modal">
      <div className="admin-receipt-header">
        <div>
          <h3 className="admin-receipt-title">{t('Biên lai thu tiền điện tử: ','Electronic receipt: ')}<code className="text-secondary">{edit.row.order_code}</code></h3>
          <p className="workspace-meta">
            <span>{edit.row.owner_username&&('@'+edit.row.owner_username+' · ')}</span>
            <span>{edit.row.amount_vnd_formatted||(edit.row.amount_vnd?.toLocaleString('vi-VN')+' đ')} · </span>
            <span style={{textTransform:'uppercase',fontWeight:600,color:edit.row.tier==='prime'?'#facc15':'#38bdf8'}}>{edit.row.tier==='prime'?'Aura Prime':'Aura Plus'}</span>
          </p>
        </div>
        <a href={`/api/v1/admin/orders/${edit.row.id}/receipt.pdf`} download={`aurameme-receipt-${edit.row.order_code}.pdf`} className="workspace-primary admin-receipt-download-btn" target="_blank" rel="noopener noreferrer">
          <Icon name="download"/>
          <span>{t('Tải PDF chính thức','Download Official PDF')}</span>
        </a>
      </div>
      <div className="admin-receipt-frame-wrap">
        <img src={`/api/v1/admin/orders/${edit.row.id}/receipt.pdf?format=png`} alt={t('Xem trước file PDF biên lai','Electronic PDF Receipt Preview')} className="admin-receipt-preview-img"/>
      </div>
   </div>}
   {edit.type==='asset-upload'&&<div className="admin-asset-upload-modal">
      <div className="admin-upload-guide">
        <strong>{t('Quy chuẩn đặt tên file bắt buộc:','Mandatory filename convention:')}</strong>
        <code>&lt;Rank&gt;_&lt;ddmmyy&gt;_&lt;stt&gt;.jpg | .png</code>
        <ul>
          <li><strong>Rank:</strong> <code>D</code>, <code>C</code>, <code>B</code>, <code>A</code> {t('hoặc','or')} <code>S</code></li>
          <li><strong>ddmmyy:</strong> {t('Ngày tháng hợp lệ (ví dụ: ','Valid calendar date (e.g. ')}<code>231126</code> = 23/11/2026)</li>
          <li><strong>stt:</strong> {t('Số thứ tự trong ngày (ví dụ: ','Sequence number (e.g. ')}<code>01</code>, <code>02</code>)</li>
          <li>{t('Ví dụ hợp lệ: ','Valid example: ')}<code>S_231126_01.jpg</code>, <code>A_231126_02.png</code></li>
        </ul>
        <p className="workspace-meta">{t('Chấp nhận file .jpg, .png đơn lẻ hoặc gói .zip chứa nhiều ảnh .jpg/.png đúng quy chuẩn. Vật phẩm mới sẽ vào hàng Chờ duyệt (Pending).','Accepts single .jpg, .png or a .zip archive containing compliant .jpg/.png files. Uploaded items enter the Pending queue.')}</p>
      </div>
      <label htmlFor="admin-asset-file-input">{t('Chọn file Meme (.jpg, .png, .zip)','Select Meme file (.jpg, .png, .zip)')}
        <input id="admin-asset-file-input" type="file" accept=".jpg,.jpeg,.png,.zip" required disabled={busy} onChange={e=>setEdit({...edit,file:e.target.files?.[0]||null})}/>
      </label>
   </div>}
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
    {edit.type==='announcement-preview'&&<div className="admin-content-preview admin-announcement-preview">
      <div className="admin-content-preview-header">
        <div className="admin-content-preview-meta">
          <span className="admin-content-preview-author">@{edit.row?.actor_username||'admin'}</span>
          <span className="admin-content-preview-time">
            {stamp(edit.row?.created_at)}
            {edit.row?.published_at&&` · ${t('Phát lúc:','Broadcasted at:')} ${stamp(edit.row.published_at)}`}
            {typeof edit.row?.recipients_count==='number'&&` · ${edit.row.recipients_count} ${t('người nhận','recipients')}`}
          </span>
        </div>
        {edit.row?.status&&<span className="workspace-badge" data-status={edit.row.status}>{status(edit.row.status)}</span>}
      </div>
      <h3 className="admin-content-preview-title">{edit.row?.title}</h3>
      <div className="admin-content-preview-body" translate="no">{edit.row?.body}</div>
    </div>}
    {edit.type==='confirm'&&<><p className="admin-confirm-target">{edit.row?.display_name||edit.row?.slug||edit.row?.title||edit.row?.body}</p><p>{edit.label||t('Xác nhận thao tác này?','Confirm this action?')}</p></>}
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
       </button>
     </div>
     <textarea id="admin-announcement-body" value={edit.body} maxLength={2000} required disabled={busy} rows={6} placeholder={t('Nội dung thông báo toàn hệ thống…','Broadcast announcement body…')} onChange={e=>setEdit({...edit,body:e.target.value})}/>
     <p className="workspace-meta">{t('Thông báo sẽ được gửi tới tất cả thành viên đang hoạt động.','All active members will receive this announcement.')}</p>
     {holdingPreview&&(
       <div className="admin-hold-preview-overlay" role="region" aria-live="polite">
         <div className="admin-hold-preview-card">
           <div className="admin-hold-preview-badge">
             <Icon name="campaign" />
             <span>AuraMeme System · {t('Xem trước trực tiếp', 'Live preview')}</span>
           </div>
           <h4 className="admin-hold-preview-title">{edit.title?.trim()||t('(Chưa có tiêu đề)','(No title)')}</h4>
           <p className="admin-hold-preview-body">{edit.body?.trim()||t('(Chưa có nội dung)','(No content)')}</p>
         </div>
       </div>
     )}
   </>}
   {edit.type==='roles'&&<><p>@{edit.row.username}</p><fieldset><legend>{t('Vai trò từ DB','Database roles')}</legend>{['USER','ADMIN'].map(value=><label className="workspace-checkbox" key={value}><input type="checkbox" checked={edit.roles.includes(value)} disabled={busy||(value==='ADMIN'&&edit.row.username!=='khang_dev'&&edit.row.username!=='kien_dev')} onChange={e=>setEdit({...edit,roles:e.target.checked?[...edit.roles,value]:edit.roles.filter(r=>r!==value)})}/>{value}{value==='ADMIN'&&edit.row.username!=='khang_dev'&&edit.row.username!=='kien_dev'&&<span style={{fontSize:11,color:'var(--am-outline)',marginLeft:8}}>({t('Bảo vệ: Chỉ 2 Admin tối thượng','Protected: Max 2 Admins')})</span>}</label>)}</fieldset><p className="workspace-meta">{t('Thay đổi vai trò sẽ kết thúc các phiên của tài khoản đó.','Changing roles ends that account’s sessions.')}</p></>}
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
      {edit.type==='content-preview'||edit.type==='announcement-preview'||edit.type==='receipt-preview'?(
        <button type="button" className="workspace-primary" onClick={()=>{setEdit(null);setHoldingPreview(false);}}>{t('Đóng','Close')}</button>
      ):edit.type==='asset-preview'?(
        <>
          <button type="button" disabled={busy} onClick={()=>{setEdit(null);setHoldingPreview(false);}}>{t('Đóng','Close')}</button>
          {edit.row.kind!=='background'&&edit.row.review_status==='pending'&&(
            <>
              <button type="button" className="text-error" disabled={busy} onClick={e=>{edit.pendingAction='reject';save(e);}}>{t('Từ chối','Reject')}</button>
              <button type="button" className="workspace-primary" disabled={busy} onClick={e=>{edit.pendingAction='approve';save(e);}}>{busy?t('Đang duyệt…','Approving…'):t('Duyệt vật phẩm','Approve asset')}</button>
            </>
          )}
        </>
      ):(
        <>
          <button type="button" disabled={busy} onClick={()=>{setEdit(null);setHoldingPreview(false);}}>{t('Hủy','Cancel')}</button>
          {edit.type==='announcement'?(
            <>
              <button type="button" disabled={busy||!edit.title.trim()||!edit.body.trim()} onClick={e=>{edit.draft=true;save(e);}}>{t('Lưu bản nháp','Save draft')}</button>
              <button type="submit" className="workspace-primary" disabled={busy||!edit.title.trim()||!edit.body.trim()}>{busy?t('Đang phát…','Broadcasting…'):t('Phát thông báo','Broadcast')}</button>
            </>
          ):(
            <button type="submit" className="workspace-primary" disabled={busy}>{busy?t('Đang lưu…','Saving…'):edit.type==='contact'?t('Lưu trạng thái','Save status'):edit.type==='asset-upload'?t('Tải lên','Upload'):t('Xác nhận','Confirm')}</button>
          )}
        </>
      )}
    </div>
  </form>}</dialog>
 </div></main>;
}
