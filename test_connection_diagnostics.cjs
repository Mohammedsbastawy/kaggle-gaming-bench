const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('web_client/hud.js','utf8');
const functions=source.slice(source.indexOf('  function connectionAssessment('),source.indexOf('  function downloadReport('));
const context={window:{stream_stats:{latest:{}},stream_client:{transport:'webrtc'}}};vm.createContext(context);vm.runInContext(functions,context);
const assess=n=>context.connectionAssessment({rtt_ms:n});
assert.match(assess(undefined),/Measuring/);assert.match(assess(NaN),/Measuring/);assert.match(assess(0),/Measuring/);assert.match(assess(79),/Lower/);assert.match(assess(80),/Moderate/);assert.match(assess(159),/Moderate/);assert.match(assess(160),/High/);
context.window.stream_stats.latest={rtt_ms:200,decode_ms:0,token:'secret',ip:'private',fps:60,present_ms:NaN};
const report=context.diagnosticReport();assert.equal(report.metrics.decode_ms,0);assert.equal(report.metrics.rtt_ms,200);assert(!JSON.stringify(report).includes('secret'));assert(!('present_ms' in report.metrics));assert.equal(report.transport,'webrtc');assert(!source.includes('video_bitrate: 7000, framerate: 30'));
console.log('PASS: latency boundaries, unavailable metrics, report allowlist, and removed 30 FPS override');
