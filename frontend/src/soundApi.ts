import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {readLocal} from './localDrafts';
import {findProduction} from './locations';
import type {Cue, CueKind, FrameSound} from './soundCues';

export type Provider = 'elevenlabs' | 'fish';
export const MODELS: Record<Provider, string[]> = {
  elevenlabs: ['eleven_v4', 'eleven_v3', 'eleven_multilingual_v2'],
  fish: ['s2.1-pro', 's2.1-pro-free'],
};
export const PROVIDER_LABEL: Record<Provider, string> = {elevenlabs: 'ElevenLabs', fish: 'Fish Audio'};

export type Voice = {
  id: string;
  provider: Provider;
  name: string;
  voice_id: string;
  model: string;
  url: string;
  note: string;
  assigned: {node_id: string; title: string}[];
};
export type Hero = {id: string; title: string};
export type SoundContext = {pid: string; sid: string; heroes: Hero[]; voices: Voice[]; frames: FrameSound[]};

const json = (method: string, body: unknown) => ({
  method,
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});

/** Общий проект, герои, библиотека голосов и звук по кадрам первой (или запомненной) серии. */
export async function loadSound(projectId: string): Promise<SoundContext | null> {
  const pid = await findProduction(projectId);
  if (!pid) return null;
  const tree = await responseJson(await apiFetch('/api/productions/' + pid));
  const stored = readLocal<{pid: string; sid: string}>('studio:board-location', {pid: '', sid: ''});
  const series = tree.nodes.filter((n: {kind: string}) => n.kind === 'series');
  const sid: string =
    series.find((n: {id: string}) => stored.pid === pid && n.id === stored.sid)?.id || series[0]?.id || '';
  const [voices, frames] = await Promise.all([
    responseJson(await apiFetch(`/api/productions/${pid}/voices`)),
    sid ? responseJson(await apiFetch(`/api/productions/${pid}/series/${sid}/sound`)) : Promise.resolve([]),
  ]);
  return {
    pid,
    sid,
    heroes: tree.nodes
      .filter((n: {kind: string}) => n.kind === 'character')
      .map((n: Hero) => ({id: n.id, title: n.title})),
    voices,
    frames,
  };
}

export const addVoice = async (
  pid: string,
  body: Pick<Voice, 'provider' | 'name' | 'voice_id' | 'model' | 'url' | 'note'>
) => responseJson(await apiFetch(`/api/productions/${pid}/voices`, json('POST', body)));
export const voicePreview = async (pid: string, vid: string): Promise<string> =>
  (await responseJson(await apiFetch(`/api/productions/${pid}/voices/${vid}/preview`))).preview_url;
export const archiveVoice = async (pid: string, vid: string) =>
  responseJson(await apiFetch(`/api/productions/${pid}/voices/${vid}`, {method: 'DELETE'}));
export const assignVoice = async (pid: string, vid: string, character_node_id: string, undo = false) =>
  responseJson(
    await apiFetch(
      `/api/productions/${pid}/voices/${vid}/${undo ? 'unassign' : 'assign'}`,
      json('POST', {character_node_id})
    )
  );

export type CueBody = {
  kind: CueKind;
  text: string;
  hero_node_id: string | null;
  level_db: number | null;
  start_s: number;
  duration_s: number | null;
};
export const addCue = async (pid: string, frame: string, body: CueBody) =>
  responseJson(await apiFetch(`/api/productions/${pid}/nodes/${frame}/sound`, json('POST', body)));
export const saveCue = async (pid: string, cue: Cue, patch: Partial<CueBody>) =>
  responseJson(
    await apiFetch(
      `/api/productions/${pid}/sound/${cue.id}`,
      json('PUT', {
        kind: cue.kind,
        text: cue.text,
        hero_node_id: cue.hero_node_id,
        level_db: cue.level_db,
        start_s: cue.start_s,
        duration_s: cue.duration_s,
        ...patch,
      })
    )
  );
export const archiveCue = async (pid: string, cid: string) =>
  responseJson(await apiFetch(`/api/productions/${pid}/sound/${cid}`, {method: 'DELETE'}));
export async function uploadCueFile(pid: string, cid: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  return responseJson(
    await apiFetch(`/api/productions/${pid}/sound/${cid}/file`, {method: 'POST', body: form})
  );
}
export const linkCueAsset = async (pid: string, cid: string, asset_id: string) =>
  responseJson(await apiFetch(`/api/productions/${pid}/sound/${cid}/link-asset`, json('POST', {asset_id})));

/** Рабочий проект кадра: расходы озвучки учитываются на нём, готовый звук сам ложится в папку кадра. */
export async function frameProject(pid: string, frame: string): Promise<string> {
  const bound = await responseJson(
    await apiFetch(`/api/productions/${pid}/nodes/${frame}/open-project`, json('POST', {}))
  );
  return bound.project_id as string;
}

export type Quote = {estimated_usd: number; quote_token: string; note: string};
export const estimateVoice = async (
  pid: string,
  hero: string,
  text: string,
  project_id: string,
  voice_library_id = ''
): Promise<Quote> =>
  responseJson(
    await apiFetch(
      `/api/productions/${pid}/nodes/${hero}/voice/estimate`,
      json('POST', {text, project_id, voice_library_id})
    )
  );
export const generateVoice = async (
  pid: string,
  hero: string,
  text: string,
  project_id: string,
  quote: Quote,
  request_id: string,
  voice_library_id = ''
): Promise<{asset_id: string}> =>
  responseJson(
    await apiFetch(
      `/api/productions/${pid}/nodes/${hero}/voice/generate`,
      json('POST', {
        text,
        project_id,
        request_id,
        quote_token: quote.quote_token,
        max_cost_usd: quote.estimated_usd,
        approved: true,
        voice_library_id,
      })
    )
  );
