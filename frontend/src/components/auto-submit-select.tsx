"use client";

import type { ComponentProps } from "react";

// Submit the containing GET form, including its current dates and filters.
// No submitter is passed: report buttons must not override the form action.
export function AutoSubmitSelect(props: Omit<ComponentProps<"select">, "onChange">) {
  return (
    <select
      {...props}
      onChange={(event) => event.currentTarget.form?.requestSubmit()}
    />
  );
}
