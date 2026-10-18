/** Локальная ссылка для оценки: сервер публикует оригинал только после подтверждения запуска. */
export const localReference = (assetId: string) => 'https://studio-local.invalid/' + assetId;

export const hasLocalReferences = (request: {
  reference_urls: string[];
  video_urls?: string[];
  audio_urls?: string[];
}) =>
  [...request.reference_urls, ...(request.video_urls || []), ...(request.audio_urls || [])].some(url =>
    url.startsWith('https://studio-local.invalid/')
  );
