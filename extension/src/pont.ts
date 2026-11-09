import type { ReponseDe, VersBackground } from "./types.ts";

export function versBackground<M extends VersBackground>(message: M): Promise<ReponseDe<M>> {
  return chrome.runtime.sendMessage(message) as Promise<ReponseDe<M>>;
}
