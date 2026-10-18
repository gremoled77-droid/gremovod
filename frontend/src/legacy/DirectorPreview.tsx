// Isolated review page: no project storage, uploads, generation or API writes.
import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {FrameSelector, EMPTY_FRAME, type FrameSelection, type FrameCatalogue} from './FramePanel';
import {CameraSelector, EMPTY_CAMERA, type CameraSelection, type CameraPreset} from './CameraPanel';
import './style.css';

const data = JSON.parse(document.getElementById('director-preview-data')!.textContent!) as {
  frames: FrameCatalogue;
  cameras: CameraPreset[];
};
function DirectorPreview() {
  const [frame, setFrame] = useState<FrameSelection>(EMPTY_FRAME),
    [camera, setCamera] = useState<CameraSelection>(EMPTY_CAMERA);
  return (
    <main className="director-review">
      <header>
        <div>
          <small>AI WORKFLOW STUDIO</small>
          <h1>Студия постановки</h1>
        </div>
        <span>Предпросмотр модуля</span>
      </header>
      <p className="muted">
        Параметры → база для GPT → готовый промпт. Здесь можно проверить меню без сохранения проекта и запуска
        генерации.
      </p>
      <FrameSelector catalogue={data.frames} value={frame} onChange={setFrame} />
      <CameraSelector presets={data.cameras} value={camera} onChange={setCamera} />
    </main>
  );
}
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <DirectorPreview />
  </React.StrictMode>
);
