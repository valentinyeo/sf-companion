import { Option } from "effect";
import type { Update } from "foldkit";

import { Message } from "./message.js";
import type { AppMessage } from "./message.js";
import type { AppModel } from "./model.js";

type UpdateReturn = Update.Return<AppModel, AppMessage>;

export const update = (model: AppModel, message: AppMessage): UpdateReturn =>
  Message.match<UpdateReturn>(message, {
    SelectedKpiWindow: ({ window }) => ({
      model: { ...model, kpiWindow: window },
    }),
    TickedClock: ({ nowMs }) => ({
      model: { ...model, nowMs: Option.some(nowMs) },
    }),
  });
