#target illustrator
/* GC21_NATIVE_FOUR_ARTBOARD_V0_1
   Exact accepted greeting card candidate: STANDARD / PORTRAIT / HERASYMENKO.
   All artboards are created by native Illustrator API. No PDF import.
   PRIVATE generated instance embeds text; never commit generated JSX.
   No dialogs, no automation launch, no production publication, no overwrites.
*/
(function () {
    var scene = /*__GC21_SCENE_JSON__*/;
    var document = null;
    var root = (new File($.fileName)).parent;
    var target = new Folder(root.fsName + '/out');
    var state = 'BLOCKED';
    var reason = '';
    var active = false;
    var PT = 72 / 25.4;
    var W = 214 * PT;
    var H = 301 * PT;
    var GAP = 18 * PT;
    var levels = [];
    function must(value, error) { if (!value) { throw new Error(error); } }
    function pt(value) { return value * PT; }
    function artLeft(page) { return (page - 1) * (W + GAP); }
    function frontFont(name) { return app.textFonts.getByName(name); }
    function rgb(color) {
        var c = new RGBColor();
        c.red = (color >> 16) & 255;
        c.green = (color >> 8) & 255;
        c.blue = color & 255;
        return c;
    }
    function addLayer(name, page) {
        var l = document.layers.add();
        l.name = name;
        // Layer.name is the stable trace ID; Layer.note is not part of Illustrator DOM.
        return l;
    }
    function imageRank(layer) {
        if (layer.role.indexOf('.PAPER') >= 0 || layer.role.indexOf('.LOCKED_BASE') >= 0) { return 0; }
        if (layer.role.indexOf('.ACCEPTED_PORTRAIT') >= 0 || layer.role.indexOf('.WATERMARK') >= 0) { return 10; }
        if (layer.role.indexOf('.FRAME') >= 0) { return 20; }
        if (layer.role.indexOf('.SENDER_LOGO') >= 0 || layer.role.indexOf('.SIGNATURE') >= 0) { return 30; }
        return 15;
    }
    function place(layerSpec) {
        var file = new File(root.fsName + '/' + layerSpec.file);
        must(file.exists, 'MISSING_ASSET_' + layerSpec.role);
        var b = layerSpec.bbox_mm;
        must(b.length === 4 && b[2] > b[0] && b[3] > b[1], 'BAD_ASSET_BBOX');
        var layer = addLayer(layerSpec.role, layerSpec.page);
        var item = document.placedItems.add();
        item.file = file;
        item.position = [artLeft(layerSpec.page) + pt(b[0]), H - pt(b[1])];
        item.width = pt(b[2]-b[0]);
        item.height = pt(b[3]-b[1]);
        item.name = layerSpec.role;
        item.move(layer, ElementPlacement.PLACEATBEGINNING);
        item.embed(); // Native embedded image; never depend on a remote linked file.
        layer.locked = (layerSpec.locked === true);
        levels.push(layerSpec.role);
    }
    function setFont(frame, font, size, color) {
        var attr = frame.textRange.characterAttributes;
        attr.textFont = font;
        attr.size = size;
        attr.fillColor = rgb(color);
    }
    function createFrontTitle(font) {
        var layer = addLayer('P01.OCCASION_TEXT_LIVE', 1);
        // Two source-authorized title rows at the canonical STANDARD occasion zone.
        var topBaselines = [222.0, 243.0];
        for (var i = 0; i < scene.front_lines.length; i++) {
            var frame = document.textFrames.pointText([artLeft(1)+pt(107.0), H-pt(topBaselines[i])]);
            frame.move(layer, ElementPlacement.PLACEATBEGINNING);
            frame.name = 'P01.OCCASION_LINE_0' + (i+1);
            frame.contents = scene.front_lines[i];
            setFont(frame,font,52, (96<<16) + (57<<8) + 19);
            frame.textRange.paragraphAttributes.justification = Justification.CENTER;
        }
        levels.push('P01.OCCASION_TEXT_LIVE');
    }
    function createGreeting(font) {
        var layer = addLayer('P04.GREETING_LIVE_AREA_TEXT', 4);
        var rect = document.pathItems.rectangle(H-pt(32), artLeft(4)+pt(32), pt(150), pt(180));
        rect.move(layer, ElementPlacement.PLACEATBEGINNING);
        rect.stroked=false; rect.filled=false;
        var area = document.textFrames.areaText(rect);
        area.name = 'P04.GREETING_AREATEXT_SOURCE';
        area.contents = String(scene.greeting_text).replace(/\r\n?/g,'\n').replace(/\n/g,'\r');
        setFont(area,font,pt(7), scene.greeting_rgb);
        var chars = area.textRange.characterAttributes;
        chars.autoLeading=false;
        chars.leading=pt(8);
        area.textRange.paragraphAttributes.justification=Justification.CENTER;
        area.textRange.paragraphAttributes.spaceAfter=0;
        area.textRange.paragraphAttributes.spaceBefore=0;
        app.redraw();
        // GC17.2 uses two reserved visual line slots: no typography redesign.
        var visibleRows=area.lines.length;
        var effectiveHeight=pt(180)-2*pt(8);
        must(visibleRows>0 && visibleRows*pt(8) < effectiveHeight,'GREETING_OVERSIZE_REVIEW_REQUIRED');
        area.paragraphs[0].paragraphAttributes.spaceBefore=Math.max(0,(effectiveHeight-visibleRows*pt(8))/2);
        must(String(area.contents).replace(/\s/g,'') === String(scene.greeting_text).replace(/\s/g,''),
             'GREETING_TEXT_FIDELITY');
        levels.push('P04.GREETING_LIVE_AREA_TEXT');
    }
    function createSender(font) {
        var layer=addLayer('P04.HERASYMENKO_LIVE_SENDER_LINES',4);
        for(var i=0;i<scene.sender_lines.length;i++){
            var s=scene.sender_lines[i];
            var frame=document.textFrames.pointText([
                artLeft(4)+pt(s.x_mm), H-pt(s.baseline_from_top_mm)]);
            frame.move(layer, ElementPlacement.PLACEATBEGINNING);
            frame.name=s.id;
            frame.contents=s.text;
            setFont(frame,font,s.size_pt,s.rgb);
        }
        levels.push('P04.HERASYMENKO_LIVE_SENDER_LINES');
    }
    function resultFile() {
        return new File(target.fsName + '/result.json');
    }
    function quoteJson(value) {
        // Adobe ExtendScript ES3 does not guarantee the JSON global.
        // Encode control characters, backslash and quote without external libraries.
        var str = String(value);
        return '"' + str.replace(/[\x00-\x1f\\"]/g, function(ch) {
            if (ch === '"') { return '\\"'; }
            if (ch === '\\') { return '\\\\'; }
            if (ch === '\n') { return '\\n'; }
            if (ch === '\r') { return '\\r'; }
            if (ch === '\t') { return '\\t'; }
            var h = ch.charCodeAt(0).toString(16);
            return '\\u' + ('0000' + h).slice(-4);
        }) + '"';
    }
    function writeResult(outcome, code) {
        if(!target.exists){return;}
        var p=resultFile();
        if(p.exists || !p.open('w')){return;}
        p.encoding='UTF-8';
        var success=(outcome==='NATIVE_AI_REOPENED_REVIEW_REQUIRED');
        var body='{'
            +'"schema":'+quoteJson('gdl_gc21_native_illustrator_result_v0_1')+','
            +'"state":'+quoteJson(outcome)+','
            +'"error":'+quoteJson(code)+','
            +'"artboards":4,'
            +'"layer_count":'+levels.length+','
            +'"ai_reopened":'+(success?'true':'false')+','
            +'"visual_approval":false,"production_ready":false}';
        p.write(body);
        p.close();
    }
    try {
        must(scene.schema_version === 'gdl_gc21_native_four_artboards_scene_v0_1','BAD_SCHEMA');
        must(scene.pages === 4 && scene.sender_variant === 'HERASYMENKO' &&
             scene.front_family === 'STANDARD' && scene.inside_image_mode === 'PORTRAIT','SCOPE_CHANGED');
        must(!target.exists,'OUTPUT_EXISTS_NO_OVERWRITE');
        must(scene.layers.length >= 10 && scene.sender_lines.length === 4 &&
             scene.front_lines.length === 2,'SOURCE_ELEMENTS_MISSING');
        var titleFont=frontFont('MonotypeCorsiva');
        var greetingFont=frontFont('ZapfChanceryC');
        must(titleFont && greetingFont,'EXACT_FONTS_MISSING');
        for(var k=0;k<scene.layers.length;k++){
            var inp=new File(root.fsName+'/'+scene.layers[k].file);
            must(inp.exists,'MISSING_ASSET_'+scene.layers[k].role);
        }
        must(target.create(),'CANNOT_CREATE_PRIVATE_OUTPUT');
        document=app.documents.add(DocumentColorSpace.RGB,W,H);
        document.artboards[0].artboardRect=[0,H,W,0];
        for(var page=2;page<=4;page++) {
            document.artboards.add([artLeft(page),H,artLeft(page)+W,0]);
        }
        must(document.artboards.length===4,'ARTBOARD_COUNT');
        // Always position elements bottom-to-top by their semantic role, not list order.
        var layers=scene.layers.slice(0);
        layers.sort(function(a,b){
            if(a.page!==b.page){return a.page-b.page;}
            return imageRank(a)-imageRank(b);
        });
        for(k=0;k<layers.length;k++){place(layers[k]);}
        createFrontTitle(titleFont);
        createGreeting(greetingFont);
        createSender(greetingFont);
        must(document.textFrames.length===7,'NATIVE_TEXT_COUNT_MISMATCH');
        var ai=new File(target.fsName+'/design.ai');
        var pdf=new File(target.fsName+'/review.pdf');
        must(!ai.exists && !pdf.exists,'EXISTING_ARTIFACT');
        var save=new IllustratorSaveOptions();
        save.pdfCompatible=true;
        save.compressed=true;
        document.saveAs(ai,save);
        must(ai.exists && ai.length>1000,'AI_SAVE_MISSING');
        var pdfOpts=new PDFSaveOptions();
        pdfOpts.artboardRange='1-4';
        document.saveAs(pdf,pdfOpts);
        must(pdf.exists && pdf.length>1000,'PDF_SAVE_MISSING');
        for(var q=0;q<4;q++){
            document.artboards.setActiveArtboardIndex(q);
            var png=new File(target.fsName+'/preview_p0'+(q+1));
            var opt=new ExportOptionsPNG24();
            opt.artBoardClipping=true;
            opt.transparency=false;
            opt.antiAliasing=true;
            opt.horizontalScale=100;
            opt.verticalScale=100;
            document.exportFile(png,ExportType.PNG24,opt);
            var pngReady=new File(target.fsName+'/preview_p0'+(q+1)+'.png');
            must(pngReady.exists && pngReady.length>1000,'PNG_EXPORT_MISSING_P0'+(q+1));
        }
        document.close(SaveOptions.DONOTSAVECHANGES);
        document=null;
        var reopened=app.open(ai);
        must(reopened.artboards.length===4,'AI_REOPEN_ARTBOARD_COUNT');
        must(reopened.textFrames.length===7,'AI_REOPEN_TEXT_COUNT');
        must(reopened.textFrames.getByName('P04.GREETING_AREATEXT_SOURCE').kind===TextType.AREATEXT,
             'AI_REOPEN_NOT_NATIVE_AREA_TEXT');
        reopened.close(SaveOptions.DONOTSAVECHANGES);
        state='NATIVE_AI_REOPENED_REVIEW_REQUIRED';
        writeResult(state,'NONE');
    } catch(error) {
        reason=String(error.message || error);
        state='BLOCKED_REVIEW_PARTIAL_OUTPUT';
        writeResult(state,reason);
        // Intentionally no automatic cleanup/retry. Preserve evidence.
    }
})();
