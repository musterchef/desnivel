const assert = require('node:assert/strict');
const {sessionModel, sendCommand} = require('../../src/desnivel/viewer/session.js');

const state = {
  configuration: {name: 'ambient', path: '/tmp/ambient.json'},
  controls: {edit_allowed: true, transport_connected: true},
  setup: {status: 'waiting', step: 'destination', tracks: [{name: '<script>test</script>', choice: 2}]},
};
const ready = sessionModel({session: state, age_s: .5});
assert.equal(ready.configuration.name, 'ambient');
assert(ready.editable && ready.transportConnected && ready.waiting);
assert.equal(ready.tracks[0].name, '<script>test</script>');
const stale = sessionModel({session: state, age_s: 5});
assert(!stale.editable && !stale.transportConnected);
assert.throws(() => sessionModel({}), /Stato/);
(async () => {
  let request;
  const result = await sendCommand({action: 'setup_reply', value: '2'}, async (path, options) => {
    request = {path, options};
    return {ok: true, json: async () => ({queued: true})};
  });
  assert(result.queued);
  assert.equal(request.path, '/api/control');
  assert.deepEqual(JSON.parse(request.options.body), {action: 'setup_reply', value: '2'});
  await assert.rejects(sendCommand({action: 'setup_save'}, async () => ({ok: false, json: async () => ({error: 'coda piena'})})), /coda piena/);
  console.log('session_panel: stato condiviso, dati scaduti e comandi HTTP verificati');
})().catch(error => { console.error(error); process.exitCode = 1; });
