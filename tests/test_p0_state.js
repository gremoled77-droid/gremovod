// GremoVOD P0 emergency tests: runs actual Python SQLite isolation suite from Node.
// No network, no providers, no media, no real Studio database.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const path = require('node:path');

const cwd=path.resolve(__dirname,'..');
const available=['python3','python'].find(cmd=>{
  const r=spawnSync(cmd,['--version'],{encoding:'utf8',timeout:3000});
  return r.status===0 && !r.error;
});
if (!available) throw new Error('Python 3 needed for real SQLite P0 emergency tests');
const suite=[
  'test_two_resume_clicks_only_one_wins_even_across_connections',
  'test_timeout_AFTER_submit_unknown_and_never_post_again',
  'test_budget_ceiling_and_total_call_count',
  'test_prompt_or_profile_changed_after_approval_is_rejected',
  'test_provider_success_charges_once_and_no_duplicate_callbacks',
  'test_no_legacy_job_overwrite_from_p0_submit',
  'test_source_changed_before_submit_blocks_billing'
];
for (const name of suite) {
  test(name,()=>{
    const proc=spawnSync(available,
      ['-m','unittest','-q',`backend.test_p0_control.P0SafetyTests.${name}`],
      {cwd,encoding:'utf8',timeout:20000,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
    assert.equal(proc.status,0,`SQLite test failed (${name}): ${proc.stderr||proc.stdout||proc.error}`);
    assert.match(proc.stderr + proc.stdout,/OK/);
  });
}
