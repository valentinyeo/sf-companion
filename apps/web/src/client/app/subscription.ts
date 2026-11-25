import { Clock, Predicate, Schema, Stream } from "effect";
import { Subscription } from "foldkit";

import { Message } from "./message.js";
import type { AppMessage } from "./message.js";
import type { AppModel } from "./model.js";

const CLOCK_INTERVAL = "30 seconds";

const clockStream: Stream.Stream<AppMessage> = Stream.tick(CLOCK_INTERVAL).pipe(
  Stream.mapEffect(() => Clock.currentTimeMillis),
  Stream.map((nowMs) => Message.TickedClock({ nowMs }))
);

export const subscriptions = Subscription.make<AppModel, AppMessage>()(
  (entry) => ({
    clock: entry(
      { onUsagePage: Schema.Boolean },
      {
        modelToDependencies: (model) => ({
          onUsagePage: Predicate.isTagged("Usage")(model.route),
        }),
        dependenciesToStream: ({ onUsagePage }) =>
          onUsagePage ? clockStream : Stream.empty,
      }
    ),
  })
);
