const path = require('node:path');
const fs = require('node:fs/promises');
const {runTests} = require('@vscode/test-electron');
(async () => {
  const root = path.resolve(__dirname, '..');
  const local = path.join(root, '.test-host');
  await fs.mkdir(path.join(local, 'workspace'), {recursive: true});
  const runner = path.join(local, `host-suite-${Date.now()}.cjs`);
  await fs.copyFile(path.join(__dirname, 'host-suite.cjs'), runner);
  const executable = process.env.VSCODE_EXECUTABLE_PATH;
  await runTests({
    ...(executable ? {vscodeExecutablePath: executable} : {}),
    extensionDevelopmentPath: root,
    extensionTestsPath: runner,
    launchArgs: [
      path.join(local, 'workspace'),
      '--disable-extensions',
      '--skip-welcome',
      '--skip-release-notes',
      '--disable-workspace-trust',
      '--remote-debugging-port=19358',
      '--user-data-dir=' + path.join(local, 'profiles', String(Date.now())),
      '--extensions-dir=' + path.join(local, 'extensions'),
      '--disable-updates',
      '--disable-gpu',
    ],
    extensionTestsEnv: {MONITOR_TEST_ROOT: root},
  });
})().catch(e => {
  console.error(e);
  process.exitCode = 1;
});
