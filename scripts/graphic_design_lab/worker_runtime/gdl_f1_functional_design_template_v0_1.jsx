#target illustrator
/* ForPrint F1: synthetic editable advertising sheet. No user files, no dialogs. */
(function () {
    var taskId = 'gdl-f1-functional-design-001';
    var base = 'D:/ForPrint_Automation/GraficsDesignLab/Automation/jobs/' + taskId + '/a0001/export/';
    var ai = new File(base + 'native_probe.ai');
    var pdf = new File(base + 'preview.pdf');
    var png = new File(base + 'preview.png');
    var headline = __F1_HEADLINE__;
    var subtitle = __F1_SUBTITLE__;
    var body = __F1_BODY__;
    var footer = __F1_FOOTER__;
    var accent = [__F1_ACCENT__];
    var mm = 72 / 25.4, oldDoc = null, doc = null, reopened = null;
    var stage = 'START';
    function assertIt(x) { if (!x) throw new Error('F1_' + stage); }
    function rgb(r,g,b) { var c=new RGBColor(); c.red=r; c.green=g; c.blue=b; return c; }
    function rect(layer, name, top, left, width, height, color) {
        var p=layer.pathItems.rectangle(top,left,width,height);
        p.name=name; p.filled=true; p.stroked=false; p.fillColor=color;
        return p;
    }
    function label(layer, name, text, left, top, size, color) {
        var t=layer.textFrames.pointText([left,top]);
        t.name=name; t.contents=text;
        t.textRange.characterAttributes.size=size;
        t.textRange.characterAttributes.fillColor=color;
        return t;
    }
    try {
        if (app.documents.length) oldDoc=app.activeDocument;
        stage='OUTPUTS_MUST_BE_NEW';
        assertIt(!ai.exists && !pdf.exists && !png.exists);
        stage='CREATE_A4';
        doc=app.documents.add(DocumentColorSpace.RGB,210*mm,297*mm);
        assertIt(doc.artboards.length===1);
        var art=doc.artboards[0].artboardRect;
        var x=art[0], y=art[1], w=210*mm, h=297*mm;
        var dark=rgb(18,37,48), pale=rgb(235,248,244), white=rgb(255,255,255);
        var teal=rgb(accent[0],accent[1],accent[2]);
        stage='BUILD_LAYERS';
        var background=doc.layers[0]; background.name='01 / ФОН';
        rect(background,'full_background',y,x,w,h,pale);
        var graphics=doc.layers.add(); graphics.name='02 / ВЕКТОРНА ГРАФІКА';
        rect(graphics,'heading_band',y-17*mm,x+16*mm,178*mm,43*mm,dark);
        rect(graphics,'accent_bar',y-69*mm,x+16*mm,9*mm,137*mm,teal);
        rect(graphics,'content_panel',y-91*mm,x+33*mm,161*mm,91*mm,white);
        rect(graphics,'footer_bar',y-248*mm,x+16*mm,178*mm,2*mm,teal);
        var circle=graphics.pathItems.ellipse(y-196*mm,x+143*mm,37*mm,37*mm);
        circle.name='vector_circle'; circle.filled=true;
        circle.stroked=false; circle.fillColor=teal;
        var text=doc.layers.add(); text.name='03 / РЕДАГОВАНИЙ ТЕКСТ';
        stage='BUILD_TEXT';
        label(text,'f1_headline',headline,x+25*mm,y-32*mm,21,white);
        label(text,'f1_subtitle',subtitle,x+25*mm,y-52*mm,11,white);
        label(text,'f1_body',body,x+40*mm,y-112*mm,12,dark);
        label(text,'f1_footer',footer,x+19*mm,y-261*mm,10,dark);
        assertIt(doc.textFrames.length===4 && doc.layers.length>=3);
        stage='PNG_EXPORT';
        var pngOpts=new ExportOptionsPNG24();
        pngOpts.artBoardClipping=true; pngOpts.transparency=false;
        pngOpts.antiAliasing=true; pngOpts.horizontalScale=120; pngOpts.verticalScale=120;
        doc.exportFile(new File(base+'preview'),ExportType.PNG24,pngOpts);
        assertIt(png.exists && png.length>1000);
        stage='AI_SAVE';
        var opts=new IllustratorSaveOptions(); opts.pdfCompatible=true; opts.compressed=true;
        doc.saveAs(ai,opts); assertIt(ai.exists && ai.length>1000);
        stage='PDF_EXPORT';
        var pdfOpts=new PDFSaveOptions(); pdfOpts.preserveEditability=false;
        doc.saveAs(pdf,pdfOpts); assertIt(pdf.exists && pdf.length>1000);
        doc.close(SaveOptions.DONOTSAVECHANGES); doc=null;
        stage='REOPEN_AI_AND_EDIT';
        reopened=app.open(ai);
        assertIt(reopened.layers.length>=3 && reopened.textFrames.length===4);
        var t=reopened.textFrames.getByName('f1_headline');
        assertIt(t.kind===TextType.POINTTEXT && t.contents===headline);
        t.contents=headline+' '; t.contents=headline;
        reopened.save();
        assertIt(ai.exists && ai.length>1000);
        reopened.close(SaveOptions.DONOTSAVECHANGES); reopened=null;
        return 'FORPRINT_NATIVE_AI_REOPENED';
    } catch(e) { return 'F1_JSX_FAIL_'+stage; }
    finally {
        if(reopened) try{reopened.close(SaveOptions.DONOTSAVECHANGES);}catch(_){}
        if(doc) try{doc.close(SaveOptions.DONOTSAVECHANGES);}catch(_){}
        if(oldDoc) try{oldDoc.activate();}catch(_){}
    }
})();
