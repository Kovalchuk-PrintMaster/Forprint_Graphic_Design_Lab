#target illustrator
/* ForPrint Illustrator Studio: ONE CANONICAL FOUR-PAGE JSX RENDERER v1
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
  var PT=72/25.4,W=scene.studio_settings.page_mm[0]*PT,H=scene.studio_settings.page_mm[1]*PT,GAP=scene.studio_settings.gap_mm*PT;
  function need(cond,code){if(!cond){throw new Error(code);}}
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
  var studioTrace=new File(root.fsName+'/gc29_checkpoint_trace_r001.log');
  function trace(label){
    try {
      if(!/^[A-Z0-9_]+$/.test(label)){return;}
      if(!studioTrace.exists){
        if(!studioTrace.open('w')){return;}
        studioTrace.encoding='UTF-8';studioTrace.writeln('GC47V_TRACE_V1');studioTrace.close();
      }
      if(studioTrace.length>9500){return;}
      if(studioTrace.open('e')){studioTrace.writeln('GC47V_'+label);studioTrace.close();}
    }catch(e){}
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
    var lay=layer(v.role), b=v.bbox_mm;
    var item=D.placedItems.add(); item.file=file;
    item.position=[ax(v.page)+b[0]*PT,H-b[1]*PT];
    item.width=(b[2]-b[0])*PT;item.height=(b[3]-b[1])*PT;
    item.name=v.role; item.move(lay,ElementPlacement.PLACEATBEGINNING);
    item.embed();
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
      var b=scene.studio_settings.p03.photo_clip_mm;
      var mask=D.pathItems.rectangle(H-b[1]*PT,ax(3)+b[0]*PT,(b[2]-b[0])*PT,(b[3]-b[1])*PT);
      mask.name='P03-030.CLIP_SHAPE';mask.stroked=false;mask.filled=false;
      mask.move(g,ElementPlacement.PLACEATBEGINNING);mask.clipping=true;g.clipped=true;
    }
    lay.locked=(v.locked===true);
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
      setFont(t,titleFont,scene.studio_settings.p01.title_font_pt,scene.studio_settings.p01.title_color_hex);
      t.textRange.paragraphAttributes.justification=Justification.CENTER;
    }
  }
  // GC29 P04 pilot: source-derived font tiers, using native visible-character
  // proof rather than an arbitrary 20-line limit. No text is rewritten.
  function significantLength(frame){
    var chars=frame.textRange.characters, n=chars.length;
    while(n>0 && /^[\s\u0003]$/.test(String(chars[n-1].contents))){n--;}
    return n;
  }
  function lastVisibleOffset(frame){
    var lines=frame.lines, last=-1;
    for(var i=0;i<lines.length;i++){
      var chars=lines[i].characters;
      for(var j=0;j<chars.length;j++){
        var offset=Number(chars[j].characterOffset);
        if(!isNaN(offset) && offset>last){last=offset;}
      }
    }
    return last;
  }
  function nativeFitProof(frame){
    app.redraw();
    fitLines=frame.lines.length;
    fitVisible=lastVisibleOffset(frame)+1;
    fitCharacters=significantLength(frame);
    return fitCharacters>0 && fitVisible>=fitCharacters && fitLines>0;
  }
  // THE ONLY P04 renderer for ALL profiles: fresh frame per font tier.
  function greeting(font){
    trace('P04_FRESH_BEGIN');
    var settings=scene.studio_settings.p04;
    var lay=layer('P04.GREETING_LIVE_AREA_TEXT');
    var expected=String(scene.greeting_text).replace(/\r\n?/g,'\n').replace(/\n/g,'\r');
    function flatten(v){return String(v).replace(/[\r\n\u0003]/g,'');}
    var exact=flatten(expected);
    need(exact.length>0&&exact.length<=settings.max_chars,'STUDIO_P04_LENGTH_OUTSIDE_POLICY');
    var candidates=exact.length<=settings.long_text_threshold ? settings.short_tiers_pt : settings.long_tiers_pt;
    need(candidates.length>0&&candidates.length<=12,'STUDIO_TIER_COUNT');
    fitCharacters=exact.length;fitAttempts=0;centered=false;
    var fitted=false,t=null;
    for(var k=0;k<candidates.length;k++){
      var pt=Number(candidates[k]);
      need(pt>=10&&pt<=25,'STUDIO_TIER_VALUE');
      var box=settings.text_box_mm;
      var shape=D.pathItems.rectangle(H-box[1]*PT,ax(4)+box[0]*PT,box[2]*PT,box[3]*PT);
      shape.move(lay,ElementPlacement.PLACEATBEGINNING);shape.stroked=false;shape.filled=false;
      t=D.textFrames.areaText(shape);t.name='P04-030.GREETING_SOURCE';
      t.contents=expected;
      trace('P04_TEXT_ASSIGNED');
      // A new text frame for each size, never resize already-populated text.
      setFont(t,font,pt,settings.text_color_hex);
      t.textRange.characterAttributes.autoLeading=false;
      t.textRange.paragraphAttributes.justification=Justification.CENTER;
      t.textRange.paragraphAttributes.spaceAfter=0;
      t.textRange.paragraphAttributes.spaceBefore=0;
      fitAttempts++;fitFontPt=pt;fitLeadingMm=pt/PT*settings.leading_ratio;
      fitLines=t.lines.length;
      var visible='';for(var i=0;i<fitLines;i++){visible+=flatten(t.lines[i].contents);}
      fitVisible=visible.length;
      fitted=fitLines>0&&fitCharacters>0&&visible===exact&&
          (fitLines+settings.spare_lines)*fitLeadingMm<=box[3]-settings.height_margin_mm;
      trace('P04_NATIVE_VISIBLE_CHECK_COMPLETE');
      if(fitted){break;}
      if(k<candidates.length-1){t.remove();t=null;}
    }
    fitState=fitted?'VISIBLE_CONTENT_FITS':'FIT_UNPROVEN_REVIEW_REQUIRED';
    need(t!==null,'STUDIO_P04_FRAME_MISSING');
    need(String(t.contents).replace(/\r\n?/g,'\n')===String(scene.greeting_text).replace(/\r\n?/g,'\n'),
         'STUDIO_P04_CONTENT_FIDELITY');
    trace('P04_FRESH_DONE');
  }
  function sender(font){
    var lay=layer('P04.SENDER_LIVE_LINES');
    var baselines=scene.studio_settings.sender.baselines_mm;
    for(var i=0;i<scene.sender_lines.length;i++){
      var t=D.textFrames.pointText([ax(4)+scene.studio_settings.sender.left_x_mm*PT,H-baselines[i]*PT]);
      t.move(lay,ElementPlacement.PLACEATBEGINNING);
      t.name='P04-060.SENDER_LINE_'+(i+1);
      t.contents=scene.sender_lines[i];
      setFont(t,font,scene.studio_settings.sender.font_sizes_pt[i],scene.studio_settings.sender.text_color_hex);
    }
  }
  try{
    need(scene.schema_version==='gdl_gc29_native_scene_v0_1','GC29_BAD_SCENE');
    need(scene.pages===4&&!scene.production_ready&&!scene.visual_approved,'GC29_AUTHORITY_CHANGED');
    need(!target.exists,'GC29_OUTPUT_EXISTS_NO_OVERWRITE');
    need(target.create(),'GC29_OUTPUT_CREATE_FAILED');
    trace('JSX_ENTER');var titleFont=app.textFonts.getByName(scene.studio_settings.p01.title_font);
    var greetingFont=app.textFonts.getByName(scene.studio_settings.p04.font_name);
    need(titleFont&&greetingFont,'GC29_REQUIRED_FONTS_UNAVAILABLE');
    D=app.documents.add(DocumentColorSpace.RGB,W,H);
    D.artboards[0].artboardRect=[0,H,W,0];
    for(var j=2;j<=4;j++){D.artboards.add([ax(j),H,ax(j)+W,0]);}
    need(D.artboards.length===4,'GC29_ARTBOARD_COUNT');
    // Added layers appear above the previously created ones.
    var order={'PAPER':0,'LOCKED_BASE':0,'WATERMARK':10,'FLOWERS':15,
      'FRAME':20,'SENDER_LOGO':30,'RECIPIENT_BRANDING':35,'SIGNATURE':35};
    var L=scene.layers.slice(0); L.sort(function(a,b){
      var x=order[a.role.split('.').pop()]||0,y=order[b.role.split('.').pop()]||0;
      return a.page===b.page?x-y:a.page-b.page;
    });
    for(j=0;j<L.length;j++){place(L[j]);}
    front(titleFont);greeting(greetingFont);sender(greetingFont);
    // Remove default empty layer; otherwise it obscures operator expectations.
    for(j=D.layers.length-1;j>=0;j--){if(D.layers[j].pageItems.length===0){D.layers[j].remove();}}
    var fileAI=new File(target.fsName+'/design.ai');
    var opts=new IllustratorSaveOptions();opts.pdfCompatible=true;opts.compressed=true;
    D.saveAs(fileAI,opts);
    need(fileAI.exists&&fileAI.length>1000,'GC29_AI_MISSING');
    var filePDF=new File(target.fsName+'/review.pdf');
    var pdfopts=new PDFSaveOptions();pdfopts.artboardRange='1-4';
    D.saveAs(filePDF,pdfopts);
    need(filePDF.exists&&filePDF.length>1000,'GC29_REVIEW_PDF_MISSING');
    for(j=0;j<4;j++){
      D.artboards.setActiveArtboardIndex(j);
      var png=new File(target.fsName+'/preview_p0'+(j+1));
      var po=new ExportOptionsPNG24();po.artBoardClipping=true;po.transparency=false;
      po.antiAliasing=true;po.horizontalScale=100;po.verticalScale=100;
      D.exportFile(png,ExportType.PNG24,po);
      need((new File(png.fsName+'.png')).exists,'GC29_PREVIEW_MISSING');
    }
    D.close(SaveOptions.DONOTSAVECHANGES);D=null;
    var opened=app.open(fileAI);
    need(opened.artboards.length===4,'GC29_AI_REOPEN_ARTBOARD_MISMATCH');
    need(opened.textFrames.getByName('P04-030.GREETING_SOURCE').kind===TextType.AREATEXT,'GC29_LIVE_TEXT_MISSING');
    opened.close(SaveOptions.DONOTSAVECHANGES);
    trace('AI_REOPENED');state='AI_REOPENED_VISUAL_REVIEW_REQUIRED';
    if(fitState==='FIT_UNPROVEN_REVIEW_REQUIRED'){error='P04_GREETING_FIT_UNPROVEN_REVIEW_REQUIRED';}
  }catch(e){
    error=String(e.message||e);state='BLOCKED_REVIEW_REQUIRED';
    // Do not leave the failed untitled native document open in Illustrator.
    if(opened!==null){try{opened.close(SaveOptions.DONOTSAVECHANGES);}catch(reopenCloseError){}opened=null;}
    if(D!==null){try{D.close(SaveOptions.DONOTSAVECHANGES);}catch(cleanError){}D=null;}
  }
  safeWrite();trace('JSX_RESULT_WRITTEN');
})();
