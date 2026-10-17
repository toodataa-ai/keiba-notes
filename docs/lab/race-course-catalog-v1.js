/* Race course catalog resolver v1 (stage-only).
 * Separates immutable JRA course facts and route identifiers from simulated
 * runner data. A registered route is NOT proof of real geometry readiness.
 */
(function(root,factory){
 'use strict';
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.JraCourseCatalog=api;
})(typeof globalThis==='object'?globalThis:null,function(){
 'use strict';
 const venueAliases=Object.freeze({
   '札幌':'sapporo','函館':'hakodate','福島':'fukushima','新潟':'niigata',
   '東京':'tokyo','中山':'nakayama','中京':'chukyo','京都':'kyoto',
   '阪神':'hanshin','小倉':'kokura'
 });
 const labels=Object.freeze({single:'周回',inner:'内回り',outer:'外回り',straight:'直線',outer_to_inner:'外→内'});
 function clean(s){return String(s??'').normalize('NFKC').trim().toLowerCase()}
 function venueCode(s){
  const x=clean(s).replace(/競馬場$/,'');
  return venueAliases[x]||x;
 }
 function surfaceCode(s){
  const x=clean(s);
  if(x==='芝'||x==='turf')return 'turf';
  if(x==='ダート'||x==='ダ'||x==='dirt')return 'dirt';
  return null;
 }
 function layoutCode(s){
  const x=clean(s).replace(/\s/g,'');
  return ({'内':'inner','内回り':'inner','inner':'inner',
    '外':'outer','外回り':'outer','outer':'outer',
    '直線':'straight','straight':'straight','直':'straight',
    '外→内':'outer_to_inner','外・内':'outer_to_inner','外内':'outer_to_inner',
    'outer_to_inner':'outer_to_inner',
    '周回':'single','single':'single','通常':'single'})[x]||null;
 }
 function railCode(s){
  if(s===null||s===undefined||String(s).trim()==='')return null;
  const x=clean(s).replace(/コース$/,'').toUpperCase();
  return /^[ABCD]$/.test(x)?x:null;
 }
 function representativeRail(surface){return surface==='turf'?'A':'dirt'}
 function create(input){
  if(!input||input.catalog_id!=='jra-flat-course-templates'||!Array.isArray(input.venues))throw Error('INVALID_JRA_CATALOG');
  const views=input.venues,venueIds=new Set(),ids=new Set(),templates=[];
  for(const v of views){
   if(venueIds.has(v.code))throw Error('DUPLICATE_VENUE '+v.code);
   venueIds.add(v.code);
   if(!['left','right'].includes(v.turn))throw Error('INVALID_TURN '+v.code);
   const routes=new Set();
   for(const route of v.routes){
    const branch=route.surface+'_'+route.layout;
    if(routes.has(branch))throw Error('DUPLICATE_ROUTE '+v.code+'_'+branch);
    routes.add(branch);
    if(!['turf','dirt'].includes(route.surface))throw Error('INVALID_SURFACE');
    if(!['single','inner','outer','straight','outer_to_inner'].includes(route.layout))throw Error('INVALID_LAYOUT');
    const ds=route.distances_m;
    if(!Array.isArray(ds)||ds.length===0||new Set(ds).size!==ds.length||ds.some(d=>!Number.isInteger(d)||d<600))throw Error('INVALID_START_DISTANCE');
    if(route.layout==='outer_to_inner'&&!route.requires_exact_branch_join)throw Error('MIXED_ROUTE_NO_BRANCH_GATE');
    for(const [rail,detail] of Object.entries(route.variants)){
     if(route.surface==='dirt'&&rail!=='dirt')throw Error('DIRT_RAIL_VARIANT');
     if(route.surface==='turf'&&rail!=='A')throw Error('TURF_MUST_USE_A_REPRESENTATIVE');
     if(!Number.isFinite(detail.straight_m)&&!(route.layout==='outer_to_inner'&&detail.straight_m===null))
       throw Error('MISSING_STRAIGHT '+v.code+' '+branch+' '+rail);
     if(detail.straight_m!==null&&(detail.straight_m<=0||detail.straight_m>1000))throw Error('INVALID_STRAIGHT');
     if(route.layout!=='outer_to_inner'&&route.layout!=='straight'&&!(detail.lap_m>1000))throw Error('MISSING_LAP');
     if(route.layout==='straight'&&detail.lap_m!==null)throw Error('STRAIGHT_HAS_LAP');
     for(const distance_m of ds){
      const id=[v.code,route.surface,route.layout,rail,distance_m].join('_');
      if(ids.has(id))throw Error('DUPLICATE_RACE_TEMPLATE '+id);
      ids.add(id);
      const experimental=route.stage_experiments?.[rail+':'+distance_m]||null;
      templates.push(Object.freeze({
       id,venue_code:v.code,venue:v.name,turn:v.turn,surface:route.surface,
       layout:route.layout,layout_label:labels[route.layout],rail,
       representative_model:route.surface==='turf'?'A':'dirt',
       distance_m,lap_m:detail.lap_m,straight_m:detail.straight_m,
       elevation_m:route.elevation_m,width_m:detail.width_m,
       source_url:v.official_url,route_sections:route.route_sections||[route.layout],
       special_start:route.special_starts?.[distance_m]||null,
       start_position:null,goal_position:null,rail_boundary:null,continuous_path:null,
       stage_experiment_id:experimental,geometry_status:experimental?'stage_experiment':'geometry_untraced',
       race_data_status:'unbound',can_simulate:false
      }));
     }
    }
   }
  }
  const cache=new Map(templates.map(t=>[t.id,t]));
  function list(query={}){
   const code=query.venue!==undefined?venueCode(query.venue):query.venue_code?venueCode(query.venue_code):null;
   const surf=query.surface?surfaceCode(query.surface):null;
   const layout=query.layout?layoutCode(query.layout):null;
   return templates.filter(t=>(!code||t.venue_code===code)&&(!surf||t.surface===surf)&&
     (!layout||t.layout===layout)&&(!query.distance_m||t.distance_m===Number(query.distance_m))&&
     (!query.rail||t.rail===representativeRail(t.surface)));
  }
  function resolve(race){
   if(!race||typeof race!=='object')return {ok:false,status:'invalid_race'};
   const venue=venueCode(race.venue_code??race.venue);
   const surface=surfaceCode(race.surface),distance=Number(race.distance_m??race.distanceM);
   if(!venueIds.has(venue))return {ok:false,status:'unknown_venue',venue};
   if(!surface)return {ok:false,status:'needs_surface'};
   if(!Number.isInteger(distance)||distance<600)return {ok:false,status:'needs_distance'};
   const candidates=templates.filter(x=>x.venue_code===venue&&x.surface===surface&&x.distance_m===distance);
   if(!candidates.length)return {ok:false,status:'unsupported_course_distance',venue,surface,distance};
   const layouts=[...new Set(candidates.map(x=>x.layout))];
   const requestedLayout=race.layout?layoutCode(race.layout):null;
   if(race.layout&&!requestedLayout)return {ok:false,status:'invalid_layout',requested:race.layout,options:layouts};
   if(layouts.length>1&&!requestedLayout)
     return {ok:false,status:'needs_layout',options:layouts,venue,surface,distance};
   const compatible=candidates.filter(x=>!requestedLayout||x.layout===requestedLayout);
   if(!compatible.length)return {ok:false,status:'unsupported_layout',options:layouts};
   // Actual B/C/D letter is accepted but does not select a separate course.
   // Start geometry, turf centreline and inside/outside branch identity remain
   // explicit and may not be borrowed from another distance or layout.
   const supplied=race.rail??race.course_variant??race.courseVariant;
   const actualRail=surface==='turf'?railCode(supplied):null;
   if(surface==='turf'&&supplied!==null&&supplied!==undefined&&String(supplied).trim()!==''&&!actualRail)
     return {ok:false,status:'invalid_rail',received:supplied};
   const rail=representativeRail(surface);
   const found=compatible.find(x=>x.rail===rail);
   if(!found)return {ok:false,status:'representative_geometry_missing',rail};
   return {ok:true,status:'metadata_registered',template:found,
     actual_rail:actualRail,
     rail_approximation:surface==='turf'&&(actualRail===null||actualRail!=='A'),
     rail_policy:surface==='turf'?'A_equivalent':'native_dirt'};
  }
  function bindRace(race){
   const match=resolve(race);
   if(!match.ok)return match;
   const t=match.template;
   // B/C/D use the disclosed approximate A-equivalent topology by design,
   // but NEVER switch venue, inner/outer, turf/dirt or start distance; no
   // race can execute without explicit geometry approval.
   if(!t.can_simulate||!t.start_position||!t.continuous_path||!t.rail_boundary)
     return {ok:false,status:'geometry_not_approved',template:t,
       actual_rail:match.actual_rail,rail_approximation:match.rail_approximation,
       missing:['start_position','continuous_path','rail_boundary','source_alignment_review']};
   return {ok:true,status:'geometry_ready',template:t,race,actual_rail:match.actual_rail,rail_approximation:match.rail_approximation};
  }
  const stats=Object.freeze({venues:views.length,families:views.reduce((a,v)=>a+v.routes.length,0),
   rail_variants:views.reduce((a,v)=>a+v.routes.reduce((s,r)=>s+Object.keys(r.variants).length,0),0),
   templates:templates.length,geometry_approved:templates.filter(t=>t.can_simulate).length,
   stage_experiments:templates.filter(t=>t.stage_experiment_id).length});
  return Object.freeze({stats,templates:Object.freeze(templates),get:id=>cache.get(id)||null,
   list,resolve,bindRace,layouts:labels});
 }
 return Object.freeze({create,venueCode,surfaceCode,layoutCode,railCode});
});
