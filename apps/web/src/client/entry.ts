import { Runtime } from "foldkit";

import { entries } from "../content/entries.js";
import { view } from "../features/page.js";
import { Flags, initialModel, Model } from "./app/model.js";
import { Message } from "./app/message.js";
import { update } from "./app/update.js";

import "./site.css";

const application = Runtime.makeApplication({
  Flags,
  Model,
  container: document.querySelector("#root"),
  devTools: import.meta.env.DEV ? { Message } : false,
  init: (flags) => ({ model: initialModel(flags, entries) }),
  update,
  view,
});

Runtime.hydrate(application);
