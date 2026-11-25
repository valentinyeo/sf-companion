import { Option } from "effect";
import { Runtime } from "foldkit";

import { factoryFeed } from "../content/factory.js";
import { view } from "../features/page.js";
import { Message } from "./app/message.js";
import { Flags, initialModel, Model } from "./app/model.js";
import type { PageFlags } from "./app/model.js";
import { subscriptions } from "./app/subscription.js";
import { update } from "./app/update.js";

import "./reader.css";

const application = Runtime.makeApplication({
  Flags,
  Model,
  container: document.querySelector("#root"),
  devTools: import.meta.env.DEV ? { Message } : false,
  init: (flags: PageFlags) => ({
    model: initialModel(flags, Option.fromNullOr(factoryFeed)),
  }),
  subscriptions,
  update,
  view,
});

Runtime.hydrate(application);
