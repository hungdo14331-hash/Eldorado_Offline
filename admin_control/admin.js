const API={
 account:"/admin-control/account",
 currency:"/admin-control/grant-currency",
 character:"/admin-control/grant-character",
 item:"/admin-control/grant-item",
 audit:"/admin-control/audit"
};
let currentAccount=null;
const $=id=>document.getElementById(id);
const fmt=v=>Number(v??0).toLocaleString("en-US");

function msg(id,text,type=""){const e=$(id);e.textContent=text||"";e.className="msg "+type}
async function req(url,opt={}){const r=await fetch(url,{credentials:"same-origin",cache:"no-store",...opt});const t=await r.text();let d={};try{d=t?JSON.parse(t):{}}catch{d={raw:t}}if(!r.ok||d.STATE==="ERROR")throw new Error(d.message||d.msg||d.DESCRIPTION||("HTTP "+r.status));return d}
function showAccount(d){currentAccount=d.id||d.account||d.user_id||$("accountId").value.trim();$("vAccount").textContent=currentAccount;$("vGold").textContent=fmt(d.gold);$("vRuby").textContent=fmt(d.ruby);$("vBp").textContent=fmt(d.bp);$("vCloud").textContent=fmt(d.cloud);$("vEssence").textContent=fmt(d.essence)}
async function searchAccount(){const id=$("accountId").value.trim();if(!id){msg("searchMsg","Hãy nhập ID tài khoản.","err");return}msg("searchMsg","Đang tải...");try{const d=await req(API.account+"?id="+encodeURIComponent(id));showAccount(d);msg("searchMsg","Đã tải tài khoản "+currentAccount+".","ok");$("serverState").textContent="Admin backend đang phản hồi"}catch(e){currentAccount=null;msg("searchMsg",e.message,"err");$("serverState").textContent="Không thể gọi admin backend"}}
function target(mid){if(currentAccount)return true;msg(mid,"Hãy tìm và chọn tài khoản trước.","err");return false}
function confirmAction(text){return new Promise(resolve=>{const dlg=$("confirmBox");$("confirmText").textContent=text;const ok=()=>{cleanup();dlg.close();resolve(true)};const cancel=()=>{cleanup();dlg.close();resolve(false)};function cleanup(){$("okConfirm").removeEventListener("click",ok);$("cancelConfirm").removeEventListener("click",cancel)}$("okConfirm").addEventListener("click",ok);$("cancelConfirm").addEventListener("click",cancel);dlg.showModal()})}
async function post(url,payload){return req(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})}

async function grantCurrency(){if(!target("currencyMsg"))return;const type=$("currencyType").value,amount=Number($("currencyAmount").value);if(!Number.isInteger(amount)||amount<=0){msg("currencyMsg","Số lượng phải là số nguyên > 0.","err");return}if(!await confirmAction(`Gửi ${fmt(amount)} ${type} tới ${currentAccount}?`))return;try{const d=await post(API.currency,{target:currentAccount,type,amount});msg("currencyMsg",`${type}: ${fmt(d.before)} → ${fmt(d.after)}`,"ok");await searchAccount()}catch(e){msg("currencyMsg",e.message,"err")}}
async function grantCharacter(){if(!target("characterMsg"))return;const id=Number($("characterId").value),reason=$("characterReason").value.trim()||"ADMIN GIFT";if(!Number.isInteger(id)||id<=0){msg("characterMsg","Character ID không hợp lệ.","err");return}if(!await confirmAction(`Gửi Character ID ${id} qua mailbox tới ${currentAccount}?`))return;try{const d=await post(API.character,{target:currentAccount,character_id:id,reason});msg("characterMsg","Đã gửi nhân vật thành công"+(d.mail_sn?` — Mail SN ${d.mail_sn}`:"")+".","ok")}catch(e){msg("characterMsg",e.message,"err")}}
async function grantItem(){if(!target("itemMsg"))return;const id=Number($("itemId").value),quantity=Number($("itemQty").value);if(!Number.isInteger(id)||id<=0){msg("itemMsg","Item ID không hợp lệ.","err");return}if(!Number.isInteger(quantity)||quantity<1||quantity>99){msg("itemMsg","Số lượng phải từ 1 đến 99.","err");return}if(!await confirmAction(`Gửi Item ID ${id} × ${quantity} tới ${currentAccount}?`))return;try{const d=await post(API.item,{target:currentAccount,item_id:id,quantity,reason:"ADMIN GIFT"});msg("itemMsg","Đã gửi item thành công"+(d.mail_sn?` — Mail SN ${d.mail_sn}`:"")+".","ok")}catch(e){msg("itemMsg",e.message,"err")}}
function esc(s){return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")}
async function loadAudit(){const b=$("auditBody");b.innerHTML='<tr><td colspan="5">Đang tải...</td></tr>';try{const d=await req(API.audit),rows=Array.isArray(d.logs)?d.logs:[];b.innerHTML=rows.length?rows.map(x=>`<tr><td>${esc(x.time??"")}</td><td>${esc(x.target??"")}</td><td>${esc(x.action??"")}</td><td>${esc(x.detail??"")}</td><td>${esc(x.result??"")}</td></tr>`).join(""):'<tr><td colspan="5">Chưa có log.</td></tr>'}catch(e){b.innerHTML=`<tr><td colspan="5">${esc(e.message)}</td></tr>`}}

document.querySelectorAll(".nav").forEach(btn=>btn.addEventListener("click",()=>{document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".view").forEach(x=>x.classList.remove("active"));btn.classList.add("active");$(btn.dataset.view+"View").classList.add("active");if(btn.dataset.view==="audit")loadAudit()}));
$("searchBtn").addEventListener("click",searchAccount);
$("accountId").addEventListener("keydown",e=>{if(e.key==="Enter")searchAccount()});
$("grantCurrencyBtn").addEventListener("click",grantCurrency);
$("grantCharacterBtn").addEventListener("click",grantCharacter);
$("grantItemBtn").addEventListener("click",grantItem);
$("auditBtn").addEventListener("click",loadAudit);
