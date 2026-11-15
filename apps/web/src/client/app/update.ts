import type { Update } from "foldkit";

import { CopyEntryLink } from "./command.js";
import { Message } from "./message.js";
import type { AppMessage } from "./message.js";
import { CopyState } from "./model.js";
import type { AppModel } from "./model.js";

type UpdateReturn = Update.Return<AppModel, AppMessage>;

export const update = (model: AppModel, message: AppMessage): UpdateReturn =>
  Message.match<UpdateReturn>(message, {
    ClickedCopyEntryLink: ({ path }) => ({
      commands: [CopyEntryLink({ path })],
      model,
    }),
    CompletedCopyEntryLink: ({ copied }) => ({
      model: {
        ...model,
        copyState: copied ? CopyState.Copied() : CopyState.Failed(),
      },
    }),
    SelectedKpiWindow: ({ window }) => ({
      model: { ...model, kpiWindow: window },
    }),
  });
