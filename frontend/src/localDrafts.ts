export function readLocal<T>(key:string,fallback:T):T{try{const value=localStorage.getItem(key);return value?JSON.parse(value) as T:fallback}catch{return fallback}}
export function writeLocal(key:string,value:unknown){try{localStorage.setItem(key,JSON.stringify(value));return true}catch{return false}}
export function clearLocal(key:string){try{localStorage.removeItem(key)}catch{/* UI still works when browser storage is unavailable. */}}
