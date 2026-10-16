import {readLocal, writeLocal} from './localDrafts';

const KEY = 'gv-chatgpt-chat-url';
export const DEFAULT_CHAT_URL = 'https://chatgpt.com/';

/** Ссылка принимается только на сам ChatGPT: по ней на телефоне открывается приложение. */
export function validChatUrl(value: string): boolean {
  try {
    const u = new URL(value.trim());
    return (
      u.protocol === 'https:' && ['chatgpt.com', 'www.chatgpt.com', 'chat.openai.com'].includes(u.hostname)
    );
  } catch {
    return false;
  }
}

export function getChatUrl(): string {
  return readLocal<string>(KEY, '');
}

export function saveChatUrl(value: string): boolean {
  return writeLocal(KEY, value.trim());
}

/** Текст для вставки в чат: промпт и порядок референсов (как на сервере). */
export function copyTextFor(prompt: string, roles: string[]): string {
  const lines = [prompt.trim()];
  if (roles.length) {
    lines.push('', 'Референсы (приложить к запросу в этом порядке):');
    roles.forEach((role, i) => lines.push(`Image ${i + 1} — ${role}`));
  }
  return lines.join('\n');
}
