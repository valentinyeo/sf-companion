import { Option } from "effect";
import type { Update } from "foldkit";

import { Message } from "./message.js";
import type { AppMessage } from "./message.js";
import type { AppModel } from "./model.js";

type UpdateReturn = Update.Return<AppModel, AppMessage>;

export const update = (model: AppModel, message: AppMessage): UpdateReturn =>
  Message.match<UpdateReturn>(message, {
    SelectedBurnRange: ({ range }) => ({
      model: { ...model, burn: { ...model.burn, range, chatId: "" } },
    }),
    SelectedBurnPlan: ({ plan }) => ({
      model: { ...model, burn: { ...model.burn, plan, chatId: "" } },
    }),
    SelectedBurnChat: ({ chatId }) => ({
      model: { ...model, burn: { ...model.burn, chatId } },
    }),
    ChangedBurnStart: ({ value }) => ({
      model: { ...model, burn: { ...model.burn, start: value } },
    }),
    ChangedBurnEnd: ({ value }) => ({
      model: { ...model, burn: { ...model.burn, end: value } },
    }),
    SelectedKpiWindow: ({ window }) => ({
      model: { ...model, kpiWindow: window },
    }),
    TickedClock: ({ nowMs }) => ({
      model: { ...model, nowMs: Option.some(nowMs) },
    }),
  });
