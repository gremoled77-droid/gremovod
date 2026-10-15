export const roles={base:'основное изображение: композиция и исходная сцена',identity:'внешность и идентичность персонажа',style:'только стиль, свет, цвета и материалы',background:'фон и окружение',object:'предмет и его внешний вид',reference:'дополнительный референс; использование описано в задаче'};
export function preparePrompt(model,b){
 const refs=b.images.map((im,i)=>`Изображение ${i+1}: ${roles[im.role]||roles.reference}.`).join('\n');
 const task=b.prompt.trim();
 const preserve='Изменяй только то, что указано в задаче. Остальные особенности исходника сохраняй, если задача не требует их изменения. Роль референса ограничивает его использование; не переноси внешность из стилевого референса. Запрошенный текст воспроизведи точно.';
 if(model==='seedream')return `${task}\n\nРоли референсов в порядке загрузки:\n${refs}\n\n${preserve}\nРезультат: одно цельное изображение.`;
 if(model==='qwen')return `Отредактируй изображение по задаче: ${task}\n\nНумерация соответствует порядку входных изображений:\n${refs}\n\n${preserve}\nСоздай один итоговый кадр. Объекты и отношения между ними должны соответствовать задаче.`;
 return `ЗАДАЧА\n${task}\n\nРЕФЕРЕНСЫ\n${refs}\n\nСОХРАНИТЬ\n${preserve}\n\nВЫХОД\nОдно изображение с соотношением сторон ${b.ratio}. Композиция, свет, материалы и детали должны быть согласованы с задачей и референсами.`;
}
export function makeInput(model,b,urls){
 const prompt=b.preparedPrompt||preparePrompt(model,b);
 if(prompt.length>5000)throw Error('Итоговый промпт превышает 5000 символов. Сократите его в карточке модели.');
 const input={prompt,image_urls:urls,aspect_ratio:b.ratio,output_format:'png',nsfw_checker:true};
 if(model==='seedream')input.quality=b.resolution==='2K'?'high':'basic';
 else if(model==='qwen')Object.assign(input,{resolution:b.resolution,enhance_prompt:false});
 else throw Error('Неизвестная API модель.');
 return input;
}
