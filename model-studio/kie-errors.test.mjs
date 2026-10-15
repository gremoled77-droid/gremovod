import {test} from 'node:test';
import assert from 'node:assert/strict';
import {describeKieError} from './kie-errors.mjs';
test('текст ответа KIE сохраняется, в том числе при переносе строк PowerShell',()=>{
 assert.equal(describeKieError({stderr:'KIE API error 402: Insufficient credits\r\nAt C:\\x\\request.ps1:82 char:21\r\n+ ...'}),'KIE API error 402: Insufficient credits');
 assert.equal(describeKieError({stderr:'KIE API error 422: prompt is\r\ntoo long\r\n\r\nAt line:1'}),'KIE API error 422: prompt is too long');
 assert.equal(describeKieError({stderr:'KIE HTTP request failed (401); credentials suppressed.'}),'KIE HTTP request failed (401)');
});
test('разные причины сбоя не маскируются одним общим сообщением',()=>{
 assert.match(describeKieError(Object.assign(Error('x'),{code:'ENOENT',syscall:'spawn powershell.exe'})),/powershell\.exe/);
 assert.match(describeKieError(Object.assign(Error('x'),{killed:true,signal:'SIGTERM',stderr:''})),/150 секунд/);
 assert.match(describeKieError(new SyntaxError('bad json')),/нечитаемый/);
 assert.match(describeKieError({stderr:'Run kie-access\\connect.ps1 first, or set KIE_API_KEY.'}),/connect\.ps1/);
 assert.match(describeKieError({stderr:'Key not valid for use in specified state.'}),/тем же Windows-пользователем/);
 assert.match(describeKieError(Object.assign(Error('x'),{code:'ENOENT',syscall:'open'})),/не создала файл/);
 assert.match(describeKieError({stderr:''}),/Проверьте ключ и сеть/);
});
test('длинное сообщение обрезается',()=>{assert.ok(describeKieError({stderr:'KIE API error 500: '+'x'.repeat(2000)}).length<=300);});
