(function(){
  'use strict';

  var original=(window.adjustDays||[]).map(copyDay);
  var draft=[],selected=0,operations=[],modal=null;
  var groups=[
    {key:'morning',label:'上午',range:'08:00—12:00'},
    {key:'afternoon',label:'下午',range:'12:00—18:00'},
    {key:'evening',label:'晚上',range:'18:00 以后'},
    {key:'unscheduled',label:'待安排',range:'时间待定'}
  ];

  function $(selector,context){return (context||document).querySelector(selector)}
  function $$(selector,context){return Array.prototype.slice.call((context||document).querySelectorAll(selector))}
  function clone(value){return JSON.parse(JSON.stringify(value))}
  function copyDay(day){return {index:day.index,date:day.date||'',theme:day.theme||'',stops:(day.stops||[]).map(function(stop){return {
    place_id:stop.place_id,
    name:stop.name||'',
    arrival:stop.arrival||'',
    duration:stop.duration==null?'':String(stop.duration),
    isNew:!!stop.isNew
  }})}}
  function esc(value){return String(value==null?'':value).replace(/[&<>"']/g,function(char){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]})}
  function uid(){return 'new-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7)}
  function currentDay(){return draft[selected]}
  function timeValue(value){var match=String(value||'').match(/(\d{1,2})[:：](\d{2})/);return match?String(match[1]).padStart(2,'0')+':'+match[2]:''}
  function minutes(value){var match=timeValue(value).match(/(\d{2}):(\d{2})/);return match?Number(match[1])*60+Number(match[2]):1441}
  function period(stop){var value=timeValue(stop.arrival),minute=minutes(value);if(!value)return 'unscheduled';return minute<720?'morning':minute<1080?'afternoon':'evening'}
  function sortByArrival(day){day.stops=day.stops.map(function(stop,index){return {stop:stop,index:index}}).sort(function(a,b){var am=minutes(a.stop.arrival),bm=minutes(b.stop.arrival);return am===bm?a.index-b.index:am-bm}).map(function(item){return item.stop})}
  function record(operation){operations=operations.filter(function(item){return !(item.type===operation.type&&item.day===operation.day&&item.placeId===operation.placeId)});operations.push(operation)}
  function stopById(id){var day=currentDay();return day&&day.stops.find(function(stop){return stop.place_id===id})}
  function groupStops(day){var result={morning:[],afternoon:[],evening:[],unscheduled:[]};(day.stops||[]).forEach(function(stop){result[period(stop)].push(stop)});return result}
  function originalStop(dayIndex,id){var day=original[dayIndex];return day&&day.stops.find(function(stop){return stop.place_id===id})}

  function renderTabs(){
    $('.adjust-days',modal).innerHTML=draft.map(function(day,index){return '<button type="button" class="adjust-day-tab '+(index===selected?'is-active':'')+'" data-day="'+index+'"><strong>Day '+esc(day.index)+'</strong><small>'+esc(day.date||'日期待定')+'</small></button>'}).join('');
  }

  function row(stop,position,total){
    var upDisabled=position<=0?' disabled':'',downDisabled=position>=total-1?' disabled':'';
    return '<article class="adjust-row" data-place="'+esc(stop.place_id)+'">'
      +'<span class="adjust-move"><button type="button" data-move="up" aria-label="上移"'+upDisabled+'>↑</button><button type="button" data-move="down" aria-label="下移"'+downDisabled+'>↓</button></span>'
      +'<label class="adjust-field adjust-time"><span>开始</span><input data-field="arrival" type="time" value="'+esc(timeValue(stop.arrival))+'" aria-label="开始时间"></label>'
      +'<label class="adjust-field adjust-place"><span>地点</span><input class="adjust-name" data-field="name" value="'+esc(stop.name)+'" aria-label="地点名称"></label>'
      +'<label class="adjust-field adjust-duration"><span>持续（分钟）</span><input data-field="duration" type="number" min="0" max="1440" step="15" value="'+esc(stop.duration)+'" aria-label="持续时间（分钟）"></label>'
      +'<button type="button" class="adjust-remove" data-remove aria-label="删除地点">×</button></article>';
  }

  function renderTimeline(){
    var day=currentDay(),bucket=groupStops(day),html='',displayPosition=0;
    groups.forEach(function(group){
      var stops=bucket[group.key];
      html+='<section class="adjust-period" data-period="'+group.key+'"><header><b>'+group.label+'</b><small>'+group.range+' · '+stops.length+' 个地点</small></header>';
      if(!stops.length){html+='<p class="adjust-period-empty">暂无地点</p><button type="button" class="adjust-inline-add" data-after="">＋ 在此处添加地点</button>'}
      stops.forEach(function(stop){
        html+=row(stop,displayPosition,day.stops.length);displayPosition+=1;
        html+='<button type="button" class="adjust-inline-add" data-after="'+esc(stop.place_id)+'">＋ 在此处添加地点</button>';
      });
      html+='</section>';
    });
    $('.adjust-timeline',modal).innerHTML=html;
    $('.adjust-theme input',modal).value=day.theme||'';
  }

  function renderRequest(){
    var day=currentDay(),source=original[selected]||{stops:[]},lines=[],sourceIds=source.stops.map(function(stop){return stop.place_id}),draftIds=day.stops.map(function(stop){return stop.place_id});
    if((day.theme||'')!==(source.theme||''))lines.push('请将 Day '+day.index+' 的当日主题改为“'+(day.theme||'未命名')+'”。');
    if(sourceIds.join('|')!==draftIds.join('|'))lines.push('请将 Day '+day.index+' 的地点顺序调整为：'+(day.stops.map(function(stop){return stop.name||'待研究地点'}).join(' → ')||'（移除全部地点）')+'。');
    source.stops.forEach(function(stop){if(draftIds.indexOf(stop.place_id)<0)lines.push('请删除 Day '+day.index+' 的“'+stop.name+'”，并同步整理路线、交通和相关行文。')});
    day.stops.forEach(function(stop){
      var old=originalStop(selected,stop.place_id),changes=[];
      if(!old)changes.push('新增地点“'+(stop.name||'请结合路线推荐')+'”');
      else{
        if(old.name!==stop.name)changes.push('地点名称改为“'+(stop.name||'待补充')+'”');
        if(timeValue(old.arrival)!==timeValue(stop.arrival))changes.push('开始时间改为 '+(timeValue(stop.arrival)||'待安排'));
        if(String(old.duration||'')!==String(stop.duration||''))changes.push('持续时间改为 '+(stop.duration||'待安排')+' 分钟');
      }
      if(changes.length)lines.push('Day '+day.index+'：'+changes.join('，')+'；请重新核验开放、预约、路线与地点来源。');
    });
    var note=$('.adjust-freeform textarea',modal).value.trim();
    if(note)lines.push('补充要求：'+note);
    $('.adjust-request textarea',modal).value=lines.join('\n')||'尚未记录修改。';
    $('.adjust-status',modal).textContent=lines.length+' 项修改已记录。';
  }

  function render(){renderTabs();renderTimeline();renderRequest()}

  function insertPlace(after,kind,name,time,duration){
    var day=currentDay(),id=uid(),stop={place_id:id,name:name||'待研究的'+kind,arrival:time||'',duration:duration||'',isNew:true};
    var index=after?day.stops.findIndex(function(item){return item.place_id===after})+1:day.stops.length;
    if(index<1)index=day.stops.length;
    day.stops.splice(index,0,stop);
    if(time)sortByArrival(day);
    record({type:'add',day:day.index,placeId:id,sentence:'请在 Day '+day.index+' 增加'+kind+'“'+stop.name+'”，开始时间 '+(time||'由 Agent 安排')+'，持续 '+(duration||'由 Agent 建议')+' 分钟，并重新研究后加入手册。'});
    render();
  }

  function openInlineForm(button){
    $$('.adjust-inline-form',modal).forEach(function(form){form.remove()});
    var form=document.createElement('div');
    form.className='adjust-inline-form';
    form.dataset.after=button.dataset.after||'';
    form.innerHTML='<label>开始时间<input data-inline-time type="time" aria-label="新增地点开始时间"></label><label>地点<input data-inline-name placeholder="地点名称" aria-label="新增地点名称"></label><label>持续（分钟）<input data-inline-duration type="number" min="0" max="1440" step="15" placeholder="例如：90" aria-label="新增地点持续时间"></label><button type="button" data-inline-save>加入</button><button type="button" class="adjust-inline-cancel" data-inline-cancel>取消</button>';
    button.replaceWith(form);
    $('input[data-inline-name]',form).focus();
  }

  function addFromForm(){
    var form=$('.adjust-add-form',modal),kind=$('select',form).value||'景点';
    insertPlace(modal.dataset.after||'',kind,$('input[data-name]',form).value.trim(),$('input[data-time]',form).value,$('input[data-duration]',form).value);
    modal.dataset.after='';
    $('input[data-name]',form).value='';$('input[data-time]',form).value='';$('input[data-duration]',form).value='';
  }

  function formatMinutes(value){value=Math.max(0,Math.min(1439,value));return String(Math.floor(value/60)).padStart(2,'0')+':'+String(value%60).padStart(2,'0')}
  function durationMinutes(stop){var value=Number(stop&&stop.duration);return Number.isFinite(value)&&value>0?value:60}
  function updateSwapTimes(first,second,direction){
    var earlier=direction==='up'?second:first, later=direction==='up'?first:second;
    var earlierTime=timeValue(earlier.arrival),laterTime=timeValue(later.arrival);
    if(!earlierTime&&!laterTime)return;
    var earlierStart=earlierTime?minutes(earlierTime):Math.max(0,minutes(laterTime)-durationMinutes(earlier)-15);
    var laterStart=laterTime?minutes(laterTime):earlierStart+durationMinutes(earlier)+15;
    var gap=Math.max(15,laterStart-earlierStart-durationMinutes(earlier));
    if(direction==='up'){
      first.arrival=formatMinutes(earlierStart);
      second.arrival=formatMinutes(earlierStart+durationMinutes(first)+gap);
    }else{
      second.arrival=formatMinutes(earlierStart);
      first.arrival=formatMinutes(earlierStart+durationMinutes(second)+gap);
    }
  }
  function moveInDay(id,direction){
    var day=currentDay(),stop=stopById(id),bucket=groupStops(day),ordered=[];
    groups.forEach(function(group){ordered=ordered.concat(bucket[group.key])});
    var position=ordered.findIndex(function(item){return item.place_id===id}),next=position+(direction==='up'?-1:1);
    if(position<0||next<0||next>=ordered.length)return;
    var target=ordered[next];updateSwapTimes(stop,target,direction);ordered[position]=target;ordered[next]=stop;day.stops=ordered;sortByArrival(day);
    record({type:'reorder',day:day.index,placeId:'day-order',sentence:'请将 Day '+day.index+' 的地点顺序调整为：'+day.stops.map(function(item){return item.name}).join(' → ')+'，并同步重算地点间交通。'});
    render();
  }

  function removePlace(id){
    var day=currentDay(),index=day.stops.findIndex(function(stop){return stop.place_id===id});if(index<0)return;
    var stop=day.stops.splice(index,1)[0];
    operations=operations.filter(function(operation){return !(operation.type==='add'&&operation.placeId===id)});
    if(!stop.isNew)record({type:'delete',day:day.index,placeId:id,sentence:'请删除 Day '+day.index+' 的“'+stop.name+'”，并同步整理路线、交通和相关行文。'});
    render();
  }

  function updateRowField(input){
    var rowEl=input.closest('[data-place]'),stop=rowEl&&stopById(rowEl.dataset.place);if(!stop)return;
    var field=input.dataset.field,value=input.value;
    stop[field]=value;
    if(field==='arrival')sortByArrival(currentDay());
    record({type:'edit',day:currentDay().index,placeId:stop.place_id,sentence:'请修改 Day '+currentDay().index+' 的“'+stop.name+'”信息。'});
    if(field==='arrival')render();else renderRequest();
  }

  function reset(){draft=original.map(copyDay);selected=0;operations=[];if(modal){modal.dataset.after='';$('.adjust-freeform textarea',modal).value='';}}
  function close(){if(!modal)return;modal.hidden=true;document.body.style.overflow='';}
  function open(){reset();modal.hidden=false;document.body.style.overflow='hidden';render();$('.itinerary-customizer__close',modal).focus()}

  function copyRequest(){
    var value=$('.adjust-request textarea',modal).value,button=$('[data-copy]',modal);
    if(!value||value==='尚未记录修改。')return;
    function done(){button.textContent='已复制';setTimeout(function(){button.textContent='复制修改申请'},1200)}
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(value).then(done).catch(function(){$('.adjust-request textarea',modal).select()})}else{$('.adjust-request textarea',modal).select()}
  }

  function init(){
    if(!document.getElementById('open-adjust-modal'))return;
    modal=document.createElement('div');modal.id='itinerary-customizer';modal.className='itinerary-customizer';modal.hidden=true;
    modal.innerHTML='<section class="itinerary-customizer__panel" role="dialog" aria-modal="true" aria-labelledby="adjust-title"><header class="itinerary-customizer__head"><div><small>ITINERARY DRAFT</small><h2 id="adjust-title">调整每日行程</h2><p>直接编辑地点、开始时间和持续时间；新增地点时填写完整信息，行程会按开始时间重新排列。</p></div><button type="button" class="itinerary-customizer__close" aria-label="关闭">×</button></header><div class="adjust-days"></div><section class="adjust-step"><header><b>01</b><span>当日行程</span></header><div class="adjust-theme"><label>当日主题</label><input aria-label="修改当日主题"></div><div class="adjust-timeline"></div></section><section class="adjust-step"><header><b>02</b><span>添加地点</span></header><div class="adjust-add-form"><label>类型<select><option>景点</option><option>餐厅</option><option>购物或店铺</option><option>当地特色体验</option><option>其他地点</option></select></label><label>地点名称<input data-name placeholder="例如：一家书店"></label><label>开始时间<input data-time type="time"></label><label>持续时间（分钟）<input data-duration type="number" min="0" max="1440" step="15" placeholder="例如：90"></label><button type="button" class="adjust-add-button">加入当天</button></div></section><section class="adjust-step adjust-freeform"><header><b>03</b><span>补充要求</span><small>选填</small></header><label>其他调整<textarea placeholder="例如：这一天不要太赶"></textarea></label></section><section class="adjust-step adjust-request"><header><b>04</b><span>修改申请</span></header><label>发送给 Agent 的提示词<textarea readonly></textarea></label><div class="adjust-actions"><button type="button" class="adjust-primary" data-copy>复制修改申请</button><button type="button" class="adjust-secondary" data-cancel>取消编辑</button></div><p class="adjust-status" aria-live="polite"></p></section></section>';
    document.body.appendChild(modal);
    document.getElementById('open-adjust-modal').addEventListener('click',open);
    $('.itinerary-customizer__close',modal).addEventListener('click',close);
    $('[data-cancel]',modal).addEventListener('click',close);
    $('[data-copy]',modal).addEventListener('click',copyRequest);
    modal.addEventListener('click',function(event){
      if(event.target===modal){close();return}
      var tab=event.target.closest('[data-day]');if(tab){selected=Number(tab.dataset.day);render();return}
      var inline=event.target.closest('.adjust-inline-add');if(inline){modal.dataset.after=inline.dataset.after||'';openInlineForm(inline);return}
      var inlineCancel=event.target.closest('[data-inline-cancel]');if(inlineCancel){inlineCancel.closest('.adjust-inline-form').remove();return}
      var inlineSave=event.target.closest('[data-inline-save]');if(inlineSave){var form=inlineSave.closest('.adjust-inline-form');insertPlace(form.dataset.after||'',$('.adjust-add-form select',modal).value||'景点',$('input[data-inline-name]',form).value.trim(),$('input[data-inline-time]',form).value,$('input[data-inline-duration]',form).value);return}
      var rowEl=event.target.closest('[data-place]');if(rowEl){if(event.target.closest('[data-remove]')){removePlace(rowEl.dataset.place);return}var move=event.target.closest('[data-move]');if(move&&!move.disabled){moveInDay(rowEl.dataset.place,move.dataset.move);return}}
      if(event.target.closest('.adjust-add-button')){addFromForm();return}
    });
    modal.addEventListener('input',function(event){
      if(event.target.matches('.adjust-theme input')){currentDay().theme=event.target.value;record({type:'title',day:currentDay().index,placeId:'day-title',sentence:'请修改 Day '+currentDay().index+' 的当日主题。'});renderRequest();return}
      if(event.target.matches('.adjust-freeform textarea')){renderRequest();return}
      if(event.target.matches('.adjust-row [data-field="name"], .adjust-row [data-field="duration"]'))updateRowField(event.target);
    });
    modal.addEventListener('change',function(event){if(event.target.matches('.adjust-row [data-field="arrival"]'))updateRowField(event.target)});
    document.addEventListener('keydown',function(event){if(event.key==='Escape'&&!modal.hidden)close()});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
