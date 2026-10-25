#target illustrator
/* GC27_P03_DEFAULT_FLOWERS_NATIVE_PROOF_V0_1
   One-page source-locked P03 proof. NOT a full greeting card or production export.
   Preview is always private; no batch execution and no overwrite.
*/
(function () {
    var scene = /*__GC27_PRIVATE_SCENE_JSON__*/;
    var folder = (new File($.fileName)).parent;
    var target = new Folder(folder.fsName + '/out');
    var doc = null;
    var MM = 72 / 25.4;
    var W = 214 * MM;
    var H = 301 * MM;
    var outcome = 'BLOCKED_REVIEW_REQUIRED';
    var code = 'NOT_RUN';
    function must(test, name) { if (!test) { throw new Error(name); } }
    function point(value) { return Number(value) * MM; }
    function putResult() {
        if (!target.exists) { return; }
        var file = new File(target.fsName + '/result.json');
        if (file.exists || !file.open('w')) { return; }
        file.encoding='UTF-8';
        file.write(JSON.stringify({schema_version:'gdl_gc27_p03_native_proof_result_v0_1',
          state:outcome, error:code, artboards:1, expected_layers:3,
          native_full_card_supported:false, visual_approved:false,
          pdf_builder_pixel_parity_verified:false, production_ready:false}));
        file.close();
    }
    try {
        must(scene.schema_version === 'gdl_gc27_p03_default_flowers_scene_v0_1', 'BAD_SCENE');
        must(scene.page === 3 && scene.artboard_mm[0] === 214 && scene.artboard_mm[1] === 301,
             'WRONG_P03_GEOMETRY');
        must(scene.layers.length === 3 && !scene.production_ready, 'WRONG_LAYERS_OR_AUTHORITY');
        must(scene.layers[0].role === 'P03.PAPER' &&
             scene.layers[1].role === 'P03.DEFAULT_FLOWERS' &&
             scene.layers[2].role === 'P03.FRAME', 'P03_LAYER_ORDER_INVALID');
        must(!target.exists, 'OUTPUT_EXISTS_NO_OVERWRITE');
        for (var j=0;j<scene.layers.length;j++) {
            var v = scene.layers[j];
            var asset = new File(folder.fsName + '/' + v.file);
            must(asset.exists && asset.length > 0, 'P03_ASSET_MISSING');
            var b = v.bbox_mm;
            must(v.page === 3 && b.length === 4 &&
                 isFinite(b[0]) && isFinite(b[1]) &&
                 isFinite(b[2]) && isFinite(b[3]) &&
                 b[2] > b[0] && b[3] > b[1], 'P03_LAYER_GEOMETRY_INVALID');
            if (v.role === 'P03.DEFAULT_FLOWERS') {
                // Identical bounded source-overscan rule to Python.
                must(b[2]-b[0] <= 4*214 && b[3]-b[1] <= 4*301,
                     'P03_SOURCE_OVERSCAN_TOO_LARGE');
                var overlapW = Math.max(0, Math.min(214,b[2])-Math.max(0,b[0]));
                var overlapH = Math.max(0, Math.min(301,b[3])-Math.max(0,b[1]));
                must(overlapW*overlapH >= 0.10*214*301,
                     'P03_SOURCE_VISIBLE_INTERSECTION_TOO_SMALL');
            } else {
                must((v.role === 'P03.PAPER' || v.role === 'P03.FRAME') &&
                     b[0] >= -5 && b[1] >= -5 && b[2] <= 214+5 && b[3] <= 301+5,
                     'P03_FIXED_LAYER_BBOX_INVALID');
            }
        }
        must(target.create(), 'PRIVATE_RESULT_FOLDER_CREATE_FAILED');
        doc = app.documents.add(DocumentColorSpace.RGB, W, H);
        doc.artboards[0].artboardRect=[0,H,W,0];
        // Illustrator creates one default layer in each new document.
        // Reuse it for P03.PAPER; added layers stack ABOVE it.
        must(doc.layers.length === 1, 'P03_INITIAL_LAYER_COUNT_INVALID');
        for (j=0;j<scene.layers.length;j++) {
            var layerSpec=scene.layers[j];
            var layer=(j===0)?doc.layers[0]:doc.layers.add();
            layer.name=layerSpec.role;
            var placed=doc.placedItems.add();
            placed.file=new File(folder.fsName + '/' + layerSpec.file);
            placed.position=[point(layerSpec.bbox_mm[0]),H-point(layerSpec.bbox_mm[1])];
            placed.width=point(layerSpec.bbox_mm[2]-layerSpec.bbox_mm[0]);
            placed.height=point(layerSpec.bbox_mm[3]-layerSpec.bbox_mm[1]);
            placed.name=layerSpec.role;
            placed.move(layer,ElementPlacement.PLACEATBEGINNING);
            placed.embed();
            layer.locked=(layerSpec.locked === true);
        }
        must(doc.artboards.length === 1 && doc.layers.length === 3,
             'P03_NATIVE_DOCUMENT_STRUCTURE_FAILED');
        var ai=new File(target.fsName+'/p03_proof.ai');
        var pdf=new File(target.fsName+'/p03_proof.pdf');
        var png=new File(target.fsName+'/preview_p03');
        var aiOpt=new IllustratorSaveOptions();
        aiOpt.pdfCompatible=true;
        doc.saveAs(ai,aiOpt);
        must(ai.exists && ai.length > 1000,'P03_NATIVE_AI_NOT_SAVED');
        var pdfOpt=new PDFSaveOptions();
        pdfOpt.artboardRange='1';
        doc.saveAs(pdf,pdfOpt);
        must(pdf.exists && pdf.length > 1000,'P03_NATIVE_PDF_NOT_SAVED');
        var pngOpt=new ExportOptionsPNG24();
        pngOpt.artBoardClipping=true;
        pngOpt.antiAliasing=true;
        pngOpt.transparency=false;
        pngOpt.horizontalScale=100;
        pngOpt.verticalScale=100;
        doc.exportFile(png,ExportType.PNG24,pngOpt);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        doc=null;
        var reopened=app.open(ai);
        must(reopened.artboards.length === 1 && reopened.layers.length === 3,
             'P03_NATIVE_AI_REOPEN_FAILED');
        must(reopened.layers.getByName('P03.DEFAULT_FLOWERS') !== null,
             'P03_FLOWERS_EDITABLE_LAYER_MISSING');
        reopened.close(SaveOptions.DONOTSAVECHANGES);
        outcome='P03_NATIVE_AI_REOPENED_VISUAL_REVIEW_REQUIRED';
        code='NONE';
        putResult();
    } catch (err) {
        code=String(err.message || err);
        if (doc !== null) { try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (ignore) {} }
        putResult();
        // Preserve partial outputs for operator review; no automatic cleanup.
    }
})();
