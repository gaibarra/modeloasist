"use client";

import { useState } from "react";

type PeriodDateRangeFieldsProps = {
  startDate: string;
  endDate: string;
};

function computeFollowingSunday(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return value;
  }

  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const parsed = new Date(year, month, day);

  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month ||
    parsed.getDate() !== day
  ) {
    return value;
  }

  const daysUntilSunday = (7 - parsed.getDay()) % 7;
  const sunday = new Date(parsed);
  sunday.setDate(parsed.getDate() + daysUntilSunday);

  const sundayYear = sunday.getFullYear();
  const sundayMonth = String(sunday.getMonth() + 1).padStart(2, "0");
  const sundayDay = String(sunday.getDate()).padStart(2, "0");
  return `${sundayYear}-${sundayMonth}-${sundayDay}`;
}

export function PeriodDateRangeFields({ startDate, endDate }: PeriodDateRangeFieldsProps) {
  const [currentStartDate, setCurrentStartDate] = useState(startDate);
  const [currentEndDate, setCurrentEndDate] = useState(endDate);

  return (
    <>
      <label className="space-y-2 text-sm font-medium text-foreground">
        Inicio (lunes)
        <input
          type="date"
          name="start_date"
          value={currentStartDate}
          onChange={(event) => {
            const nextStartDate = event.target.value;
            setCurrentStartDate(nextStartDate);
            setCurrentEndDate(computeFollowingSunday(nextStartDate));
          }}
          className="field-input"
        />
      </label>
      <label className="space-y-2 text-sm font-medium text-foreground">
        Fin (domingo)
        <input
          type="date"
          name="end_date"
          value={currentEndDate}
          onChange={(event) => setCurrentEndDate(event.target.value)}
          className="field-input"
        />
      </label>
    </>
  );
}