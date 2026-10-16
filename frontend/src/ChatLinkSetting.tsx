import {useState} from 'react';
import {getChatUrl, saveChatUrl, validChatUrl} from './chatLink';

/** Ссылка на чат ChatGPT, куда кнопка «Отправить в ChatGPT» ведёт с телефона и компьютера. */
export default function ChatLinkSetting() {
  const [value, setValue] = useState(getChatUrl);
  const [saved, setSaved] = useState(false);
  const bad = value.trim() !== '' && !validChatUrl(value);
  return (
    <div className="chat-link-setting">
      <h3>Чат ChatGPT для картинок</h3>
      <p className="muted">
        Вставь ссылку на свой чат (chatgpt.com/c/…). Кнопка «Отправить в ChatGPT» скопирует промпт и откроет
        этот чат: на телефоне — в приложении ChatGPT. Ссылка хранится только в этом браузере.
      </p>
      <label>
        Ссылка на чат
        <input
          type="url"
          inputMode="url"
          placeholder="https://chatgpt.com/c/…"
          value={value}
          onChange={e => {
            setValue(e.target.value);
            setSaved(false);
          }}
        />
      </label>
      {bad && <p className="alert">Нужна ссылка вида https://chatgpt.com/…</p>}
      <button
        disabled={bad}
        onClick={() => {
          setSaved(saveChatUrl(value));
        }}
      >
        Сохранить
      </button>
      {saved && <span className="muted"> Сохранено</span>}
    </div>
  );
}
