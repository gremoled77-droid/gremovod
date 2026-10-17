export type ShotDirection = {
  size: string;
  subject_ids: string[] | null;
  movement: string;
  focal_mm: number | null;
  aperture: number | null;
  focus: '' | 'subject' | 'deep' | 'rack';
  note: string;
};
export type ShootingCatalogue = {
  sizes: {id: string; title: string}[];
  movements: {id: string; title: string}[];
};
const EMPTY: ShotDirection = {
  size: '',
  subject_ids: null,
  movement: '',
  focal_mm: null,
  aperture: null,
  focus: '',
  note: '',
};

export default function ShotDirectionForm({
  value,
  catalogue,
  characters,
  disabled,
  onChange,
}: {
  value?: ShotDirection | null;
  catalogue: ShootingCatalogue;
  characters: {id: string; title: string}[];
  disabled: boolean;
  onChange: (value: ShotDirection) => void;
}) {
  const shot = {...EMPTY, ...value};
  const change = (patch: Partial<ShotDirection>) => onChange({...shot, ...patch});
  return (
    <fieldset disabled={disabled} className="shot-direction">
      <legend>Постановка съёмки</legend>
      <label>
        Крупность плана · размер объекта в кадре
        <select value={shot.size} onChange={e => change({size: e.target.value})}>
          <option value="">По сценарию и референсу</option>
          {catalogue.sizes.map(p => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>Объект съёмки · персонажи в кадре</legend>
        <label className="shot-check">
          <input
            type="checkbox"
            checked={shot.subject_ids === null}
            onChange={e => change({subject_ids: e.target.checked ? null : []})}
          />
          Взять состав сцены
        </label>
        {shot.subject_ids !== null && (
          <>
            {characters.length === 0 && <p>Сначала добавь персонажей в проект.</p>}
            {characters.map(c => (
              <label className="shot-check" key={c.id}>
                <input
                  type="checkbox"
                  checked={shot.subject_ids!.includes(c.id)}
                  onChange={e =>
                    change({
                      subject_ids: e.target.checked
                        ? [...shot.subject_ids!, c.id]
                        : shot.subject_ids!.filter(id => id !== c.id),
                    })
                  }
                />
                {c.title}
              </label>
            ))}
            {shot.subject_ids.length === 0 && (
              <small>Без персонажей: предмет или окружение. Укажи объект в задаче ниже.</small>
            )}
          </>
        )}
      </fieldset>
      <label>
        Тип движения камеры
        <select value={shot.movement} onChange={e => change({movement: e.target.value})}>
          <option value="">По задаче</option>
          {catalogue.movements.map(p => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </label>
      <details>
        <summary>Уточнения задачи · объектив и фокус</summary>
        <label>
          Фокусное расстояние, мм · эквивалент полного кадра
          <input
            type="number"
            min={8}
            max={1000}
            step="any"
            placeholder="Например, 35"
            value={shot.focal_mm ?? ''}
            onChange={e => change({focal_mm: e.target.value === '' ? null : e.target.valueAsNumber})}
          />
        </label>
        <label>
          Диафрагма · f/
          <input
            type="number"
            min={0.7}
            max={64}
            step="any"
            placeholder="Например, 2.8"
            value={shot.aperture ?? ''}
            onChange={e => change({aperture: e.target.value === '' ? null : e.target.valueAsNumber})}
          />
        </label>
        <label>
          Фокус
          <select
            value={shot.focus}
            onChange={e => change({focus: e.target.value as ShotDirection['focus']})}
          >
            <option value="">По задаче</option>
            <option value="subject">На объекте съёмки</option>
            <option value="deep">Глубокая резкость</option>
            <option value="rack">Перевод фокуса · Rack focus</option>
          </select>
        </label>
        <p className="muted">
          Параметры задают визуальный замысел для промпта. Для изображения движение определяет начальный кадр,
          для видео — движение камеры.
        </p>
      </details>
      <label>
        Задача кадра и дополнительные настройки
        <textarea
          rows={3}
          maxLength={2000}
          value={shot.note}
          placeholder="На чём держать внимание, откуда и куда движется камера, свет, выдержка и другие уточнения"
          onChange={e => change({note: e.target.value})}
        />
      </label>
    </fieldset>
  );
}
