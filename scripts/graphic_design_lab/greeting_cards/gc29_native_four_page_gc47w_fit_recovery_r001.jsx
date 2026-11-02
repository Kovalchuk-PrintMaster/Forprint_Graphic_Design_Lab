#target illustrator
/* GC29_NATIVE_FOUR_PAGE_V0_1
 * True native four-page candidate. NEVER import an entire PDF page.
 * On each run use only accepted job + frozen graphic assets. All source files
 * are local to this run bundle; the AI embeds placed graphic objects.
 * NON-PRODUCTION, no customer publication, no automatic overwrite.
 */
(function(){
  var scene=/*__GC29_SCENE__*/;
  var root=(new File($.fileName)).parent;
  var target=new Folder(root.fsName+'/out');
  var D=null;
  var error='NONE';
  var state='BLOCKED_REVIEW_REQUIRED';
  var opened=null;
  var fitState='NOT_ATTEMPTED', fitFontPt=null, fitLeadingMm=null;
  var fitLines=0, fitVisible=0, fitCharacters=0, fitAttempts=0, centered=false;
  var PT=72/25.4,W=214*PT,H=301*PT,GAP=18*PT;
  function need(cond,code){if(!cond){throw new Error(code);}}
  // GC47V diagnostic: disk-backed breadcrumbs in the CURRENT local PREPRESS work folder.
  // No client text, paths, fonts, SHA, or document content are written to the trace.
  // This is an opt-in GC47T runtime template only; canonical GC29 stays unchanged.
  var traceFile=new File(root.fsName+'/gc29_checkpoint_trace_r001.log');
  var traceInitialized=false;
  function traceInit(){
    need(!traceFile.exists,'GC47V_TRACE_EXISTS_NO_OVERWRITE');
    traceFile.encoding='UTF-8';
    need(traceFile.open('w'),'GC47V_TRACE_CREATE_FAILED');
    need(traceFile.write('GC47V_TRACE_V1\n'),'GC47V_TRACE_HEADER_WRITE_FAILED');
    need(traceFile.close(),'GC47V_TRACE_HEADER_CLOSE_FAILED');
    traceInitialized=true;
  }
  function trace(phase){
    need(traceInitialized,'GC47V_TRACE_NOT_INITIALIZED');
    need(/^[A-Z0-9_]+$/.test(phase),'GC47V_TRACE_PHASE_INVALID');
    traceFile.encoding='UTF-8';
    need(traceFile.open('a'),'GC47V_TRACE_APPEND_FAILED');
    var ok=traceFile.write('GC47V_'+phase+'\n');
    var closed=traceFile.close();
    need(ok&&closed,'GC47V_TRACE_FLUSH_FAILED');
  }
  function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n')+'"';}
  function safeWrite(){
    if(!target.exists){return;}
    var path=new File(target.fsName+'/result.json');
    if(path.exists||!path.open('w')){return;}
    path.encoding='UTF-8';
    function jsonNum(v){return v===null?'null':String(v);}
    path.write('{"schema_version":"gdl_gc29_native_result_v0_1","state":'+q(state)+',"error":'+q(error)+
      ',"pages":4,"visual_approved":false,"production_ready":false,"source_pdf_runtime_used":false'+
      ',"p04_greeting_fit_state":'+q(fitState)+
      ',"p04_font_pt":'+jsonNum(fitFontPt)+',"p04_leading_mm":'+jsonNum(fitLeadingMm)+
      ',"p04_visible_chars":'+fitVisible+',"p04_total_chars":'+fitCharacters+
      ',"p04_visible_lines":'+fitLines+',"p04_fit_trials":'+fitAttempts+
      ',"p04_centering_applied":'+(centered?'true':'false')+'}');
    path.close();
  }
  function colorInt(number){
    var c=new RGBColor();c.red=(number>>16)&255;c.green=(number>>8)&255;c.blue=number&255;return c;
  }
  function layer(name){var l=D.layers.add();l.name=name;return l;}
  function ax(page){return (page-1)*(W+GAP);}
  function bboxOK(b){return b&&b.length===4&&b[2]>b[0]&&b[3]>b[1];}
  function place(v){
    need(bboxOK(v.bbox_mm),'GC29_LAYER_BBOX_INVALID');
    var file=new File(root.fsName+'/'+v.file);
    need(file.exists&&file.length>200,'GC29_GRAPHIC_ASSET_MISSING_'+v.role);
    trace('ASSET_LAYER_BEGIN');
    var lay=layer(v.role), b=v.bbox_mm;
    var item=D.placedItems.add(); item.file=file;
    item.position=[ax(v.page)+b[0]*PT,H-b[1]*PT];
    item.width=(b[2]-b[0])*PT;item.height=(b[3]-b[1])*PT;
    item.name=v.role; item.move(lay,ElementPlacement.PLACEATBEGINNING);
    trace('ASSET_EMBED_BEGIN');
    item.embed();
    trace('ASSET_EMBED_DONE');
    // GC29: floral crop deliberately uses a VECTOR mask, not the old portrait smask.
    if(v.role==='P03.FLOWERS'){
      var g=lay.groupItems.add();
      // The source image extends beyond the frame: the clip remains editable.
      var found=false;
      for(var i=lay.pageItems.length-1;i>=0;i--){
        var p=lay.pageItems[i];
        if(p!==g && (p.typename==='RasterItem'||p.typename==='PlacedItem') && p.name===v.role){
          p.move(g,ElementPlacement.PLACEATBEGINNING); found=true; break;
        }
      }
      need(found,'GC29_FLOWERS_GROUP_CONTENT_MISSING');
      var mask=D.pathItems.rectangle(H-20.854*PT,ax(3)+11*PT,(203-11)*PT,(280.1457-20.854)*PT);
      mask.name='P03-030.CLIP_SHAPE';mask.stroked=false;mask.filled=false;
      trace('P03_CLIP_BEGIN');
      mask.move(g,ElementPlacement.PLACEATBEGINNING);mask.clipping=true;g.clipped=true;
      trace('P03_CLIP_DONE');
    }
    lay.locked=(v.locked===true);
    trace('ASSET_LAYER_DONE');
  }
  function setFont(frame,font,sizePt,color){
    var ch=frame.textRange.characterAttributes;
    ch.textFont=font;ch.size=sizePt;ch.fillColor=colorInt(color);
  }
  function front(titleFont){
    var lay=layer('P01.OCCASION_TEXT_LIVE');
    for(var i=0;i<scene.front_lines.length;i++){
      var t=D.textFrames.pointText([ax(1)+107*PT,H-(222+i*21)*PT]);
      t.move(lay,ElementPlacement.PLACEATBEGINNING);
      t.name='P01-030.LINE_'+(i+1);t.contents=scene.front_lines[i];
      setFont(t,titleFont,52,0x603913);
      t.textRange.paragraphAttributes.justification=Justification.CENTER;
    }
  }
  // GC29 P04 pilot: source-derived font tiers, using native visible-character
  // proof rather than an arbitrary 20-line limit. No text is rewritten.
  // GC47W: use the natively proven GC47N/GC47O line-content comparison,
  // not the old per-character characterOffset and forced app.redraw() scan.
  // This is a NEW candidate only. Canonical GC29 is unchanged.
  function gc47wFlatten(value){return String(value).replace(/[\r\n\u0003]/g,'');}
  function gc47wVisible(frame){
    var visible='';
    for(var k=0;k<frame.lines.length;k++){
      visible+=gc47wFlatten(frame.lines[k].contents);
    }
    return visible;
  }
  function gc47wPathAnchors(frame){
    var pts=frame.textPath.pathPoints;
    need(pts.length===4,'GC47W_PATH_NOT_FOUR_CORNERS');
    var ret=[],minX=1e20,maxX=-1e20,minY=1e20,maxY=-1e20;
    for(var pidx=0;pidx<4;pidx++){
      var a=pts[pidx].anchor;
      need(a.length===2 && isFinite(a[0]) && isFinite(a[1]),'GC47W_BAD_ANCHOR');
      ret.push(a[0]);ret.push(a[1]);
      minX=Math.min(minX,a[0]);maxX=Math.max(maxX,a[0]);
      minY=Math.min(minY,a[1]);maxY=Math.max(maxY,a[1]);
    }
    // Fixed PDF zone [32,32,182,212] mm on the FOURTH artboard.
    need(Math.abs(minX-(ax(4)+32*PT))<0.1 &&
         Math.abs(maxX-(ax(4)+182*PT))<0.1 &&
         Math.abs(minY-(H-212*PT))<0.1 &&
         Math.abs(maxY-(H-32*PT))<0.1,'GC47W_FIXED_BOX_CHANGED');
    return ret;
  }
  function gc47wAnchorsSame(before,after){
    if(before.length!==after.length){return false;}
    for(var i=0;i<before.length;i++){
      if(Math.abs(before[i]-after[i])>=0.01){return false;}
    }
    return true;
  }
  function greeting(font){
    trace('P04_LAYER_BEGIN');
    var lay=layer('P04.GREETING_LIVE_AREA_TEXT');
    trace('P04_LAYER_DONE');
    trace('P04_RECT_BEGIN');
    var shape=D.pathItems.rectangle(H-32*PT,ax(4)+32*PT,150*PT,180*PT);
    shape.move(lay,ElementPlacement.PLACEATBEGINNING);
    shape.stroked=false;shape.filled=false;
    trace('P04_RECT_DONE');
    trace('P04_AREA_TEXT_BEGIN');
    var t=D.textFrames.areaText(shape);t.name='P04-030.GREETING_SOURCE';
    trace('P04_AREA_TEXT_DONE');
    var expected=String(scene.greeting_text).replace(/\r\n?/g,'\n').replace(/\n/g,'\r');
    trace('P04_TEXT_ASSIGN_BEGIN');
    t.contents=expected;
    trace('P04_TEXT_ASSIGN_DONE');
    trace('P04_FONT_ASSIGN_BEGIN');
    setFont(t,font,7*PT,0x16120e);
    trace('P04_FONT_ASSIGN_DONE');
    trace('P04_PARAGRAPH_BEGIN');
    var ch=t.textRange.characterAttributes;
    ch.autoLeading=false;
    t.textRange.paragraphAttributes.justification=Justification.CENTER;
    t.textRange.paragraphAttributes.spaceAfter=0;
    t.textRange.paragraphAttributes.spaceBefore=0;
    trace('P04_PARAGRAPH_DONE');
    trace('P04_FIDELITY_BEGIN');
    need(gc47wFlatten(t.contents)===gc47wFlatten(expected),'GC47W_TEXT_CHANGED_PRE_FIT');
    fitCharacters=gc47wFlatten(expected).length;
    trace('P04_FIDELITY_DONE');
    trace('P04_ANCHORS_BEGIN');
    var anchorBefore=gc47wPathAnchors(t);
    trace('P04_ANCHORS_DONE');
    // 0.1pt shrink-only: GC47N/GC47O native-tested strategy; 16pt is
    // a laboratory readability floor. Failure to fit is review-required.
    var initial=7*PT, step=0.1, floor=16.0;
    var maxTries=Math.ceil((initial-floor)/step)+1;
    var fitted=false;
    trace('P04_FIT_BEGIN');
    for(var k=0;k<maxTries;k++){
      fitAttempts++;
      var fontPt=Math.max(floor,initial-k*step);
      var leadingMm=(fontPt/PT)*8/7;
      if(k===0){trace('P04_FIT_FIRST_SIZE_BEGIN');}
      ch.size=fontPt;ch.leading=fontPt*8/7;
      fitFontPt=fontPt;fitLeadingMm=leadingMm;
      if(k===0){trace('P04_FIT_FIRST_SIZE_DONE');}
      if(k===0){trace('P04_FIT_FIRST_LINES_BEGIN');}
      var lineCount=t.lines.length;
      var visible=lineCount>0?gc47wVisible(t):'';
      if(k===0){trace('P04_FIT_FIRST_LINES_DONE');}
      fitLines=lineCount;fitVisible=visible.length;
      var full=visible===gc47wFlatten(expected) && lineCount>0;
      var reserved=(lineCount+2)*leadingMm <= 179.5;
      if(full && reserved){fitted=true;break;}
      if(fontPt<=floor+0.001){break;}
    }
    trace('P04_FIT_EVALUATED');
    fitState=fitted?'VISIBLE_CONTENT_FITS':'FIT_UNPROVEN_REVIEW_REQUIRED';
    trace('P04_ANCHORS_FINAL_BEGIN');
    need(gc47wAnchorsSame(anchorBefore,gc47wPathAnchors(t)),'GC47W_ANCHORS_MUTATED_BY_FIT');
    trace('P04_ANCHORS_FINAL_DONE');
    need(gc47wFlatten(t.contents)===gc47wFlatten(expected),'GC47W_TEXT_CHANGED_DURING_FIT');
    // Native GC47O proved fill WITHOUT vertical recentering; preserve box.
    // Do not use paragraph spaceBefore to shift it during this recovery pilot.
    centered=false;
    trace('P04_TEXT_VERIFIED');
  }
  function sender(font){
    var lay=layer('P04.SENDER_LIVE_LINES');
    var baselines=[227,235,243,251];
    for(var i=0;i<scene.sender_lines.length;i++){
      var t=D.textFrames.pointText([ax(4)+32*PT,H-baselines[i]*PT]);
      t.move(lay,ElementPlacement.PLACEATBEGINNING);
      t.name='P04-060.SENDER_LINE_'+(i+1);
      t.contents=scene.sender_lines[i];
      setFont(t,font,i===1?15:12,0x16120e);
    }
  }
  try{
    traceInit();trace('JSX_ENTER');
    need(scene.schema_version==='gdl_gc29_native_scene_v0_1','GC29_BAD_SCENE');
    need(scene.pages===4&&!scene.production_ready&&!scene.visual_approved,'GC29_AUTHORITY_CHANGED');
    trace('SCENE_VALIDATED');
    need(!target.exists,'GC29_OUTPUT_EXISTS_NO_OVERWRITE');
    need(target.create(),'GC29_OUTPUT_CREATE_FAILED');
    trace('OUTPUT_CREATED');
    trace('FONT_TITLE_LOOKUP_BEGIN');
    var titleFont=app.textFonts.getByName('MonotypeCorsiva');
    trace('FONT_TITLE_LOOKUP_DONE');
    trace('FONT_GREETING_LOOKUP_BEGIN');
    var greetingFont=app.textFonts.getByName('ZapfChanceryC');
    trace('FONT_GREETING_LOOKUP_DONE');
    need(titleFont&&greetingFont,'GC29_REQUIRED_FONTS_UNAVAILABLE');
    trace('DOCUMENT_CREATE_BEGIN');
    D=app.documents.add(DocumentColorSpace.RGB,W,H);
    trace('DOCUMENT_CREATE_DONE');
    trace('ARTBOARDS_BEGIN');
    D.artboards[0].artboardRect=[0,H,W,0];
    for(var j=2;j<=4;j++){D.artboards.add([ax(j),H,ax(j)+W,0]);}
    need(D.artboards.length===4,'GC29_ARTBOARD_COUNT');
    trace('ARTBOARDS_DONE');
    // Added layers appear above the previously created ones.
    var order={'PAPER':0,'LOCKED_BASE':0,'WATERMARK':10,'FLOWERS':15,
      'FRAME':20,'SENDER_LOGO':30,'RECIPIENT_BRANDING':35,'SIGNATURE':35};
    var L=scene.layers.slice(0); L.sort(function(a,b){
      var x=order[a.role.split('.').pop()]||0,y=order[b.role.split('.').pop()]||0;
      return a.page===b.page?x-y:a.page-b.page;
    });
    for(j=0;j<L.length;j++){
      trace('ASSET_BEGIN_'+j);place(L[j]);trace('ASSET_DONE_'+j);
    }
    trace('ALL_ASSETS_DONE');
    trace('P01_TEXT_BEGIN');front(titleFont);trace('P01_TEXT_DONE');
    trace('P04_GREETING_BEGIN');greeting(greetingFont);trace('P04_GREETING_DONE');
    trace('P04_SENDER_BEGIN');sender(greetingFont);trace('P04_SENDER_DONE');
    // Remove default empty layer; otherwise it obscures operator expectations.
    trace('EMPTY_LAYERS_BEGIN');
    for(j=D.layers.length-1;j>=0;j--){if(D.layers[j].pageItems.length===0){D.layers[j].remove();}}
    trace('EMPTY_LAYERS_DONE');
    var fileAI=new File(target.fsName+'/design.ai');
    var opts=new IllustratorSaveOptions();opts.pdfCompatible=true;opts.compressed=true;
    trace('AI_SAVE_BEGIN');
    D.saveAs(fileAI,opts);
    trace('AI_SAVE_DONE');
    need(fileAI.exists&&fileAI.length>1000,'GC29_AI_MISSING');
    var filePDF=new File(target.fsName+'/review.pdf');
    var pdfopts=new PDFSaveOptions();pdfopts.artboardRange='1-4';
    trace('PDF_SAVE_BEGIN');
    D.saveAs(filePDF,pdfopts);
    trace('PDF_SAVE_DONE');
    need(filePDF.exists&&filePDF.length>1000,'GC29_REVIEW_PDF_MISSING');
    for(j=0;j<4;j++){
      D.artboards.setActiveArtboardIndex(j);
      var png=new File(target.fsName+'/preview_p0'+(j+1));
      var po=new ExportOptionsPNG24();po.artBoardClipping=true;po.transparency=false;
      po.antiAliasing=true;po.horizontalScale=100;po.verticalScale=100;
      trace('PNG_EXPORT_BEGIN_'+j);
      D.exportFile(png,ExportType.PNG24,po);
      trace('PNG_EXPORT_DONE_'+j);
      need((new File(png.fsName+'.png')).exists,'GC29_PREVIEW_MISSING');
    }
    trace('DOCUMENT_CLOSE_BEGIN');
    D.close(SaveOptions.DONOTSAVECHANGES);D=null;
    trace('DOCUMENT_CLOSE_DONE');
    trace('AI_REOPEN_BEGIN');
    var opened=app.open(fileAI);
    trace('AI_REOPEN_DONE');
    need(opened.artboards.length===4,'GC29_AI_REOPEN_ARTBOARD_MISMATCH');
    need(opened.textFrames.getByName('P04-030.GREETING_SOURCE').kind===TextType.AREATEXT,'GC29_LIVE_TEXT_MISSING');
    opened.close(SaveOptions.DONOTSAVECHANGES);
    trace('AI_READBACK_DONE');
    trace('NATIVE_COMPLETE');
    state='AI_REOPENED_VISUAL_REVIEW_REQUIRED';
    if(fitState==='FIT_UNPROVEN_REVIEW_REQUIRED'){error='P04_GREETING_FIT_UNPROVEN_REVIEW_REQUIRED';}
  }catch(e){
    try{if(traceInitialized){trace('JSX_CAUGHT_EXCEPTION');}}catch(traceError){}
    error=String(e.message||e);state='BLOCKED_REVIEW_REQUIRED';
    // Do not leave the failed untitled native document open in Illustrator.
    if(opened!==null){try{opened.close(SaveOptions.DONOTSAVECHANGES);}catch(reopenCloseError){}opened=null;}
    if(D!==null){try{D.close(SaveOptions.DONOTSAVECHANGES);}catch(cleanError){}D=null;}
  }
  safeWrite();
  try{if(traceInitialized){trace('RESULT_WRITE_RETURNED');}}catch(traceError){}
})();
