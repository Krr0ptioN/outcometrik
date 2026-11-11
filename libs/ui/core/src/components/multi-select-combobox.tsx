'use client';

import * as React from 'react';
import { CheckIcon, ChevronsUpDownIcon } from 'lucide-react';
import { Popover } from 'radix-ui';
import { Button } from './button';
import { cn } from '../lib/utils';

export interface MultiSelectOption {
  value: string;
  label: string;
}

export function MultiSelectCombobox({
  id,
  label,
  options,
  value,
  onChange,
  placeholder = 'Select options…',
  searchPlaceholder = 'Search options…',
}: {
  id: string;
  label: string;
  options: MultiSelectOption[];
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  searchPlaceholder?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState('');
  const filtered = options.filter((option) =>
    option.label.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const selectedLabels = options
    .filter((option) => value.includes(option.value))
    .map((option) => option.label);

  function toggle(optionValue: string) {
    onChange(
      value.includes(optionValue)
        ? value.filter((item) => item !== optionValue)
        : [...value, optionValue],
    );
  }

  return (
    <Popover.Root
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) setSearch('');
      }}
    >
      <Popover.Trigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-label={label}
          aria-expanded={open}
          aria-controls={`${id}-options`}
          className="w-full justify-between font-normal"
        >
          <span className="truncate text-left">
            {selectedLabels.length ? selectedLabels.join(', ') : placeholder}
          </span>
          <ChevronsUpDownIcon className="size-4 shrink-0 opacity-50" aria-hidden="true" />
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={4}
          className="z-50 w-[var(--radix-popover-trigger-width)] rounded-md border bg-popover p-2 text-popover-foreground shadow-md outline-none"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            document.getElementById(`${id}-search`)?.focus();
          }}
        >
          <input
            id={`${id}-search`}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={searchPlaceholder}
            aria-label={`${label} search`}
            className="mb-2 h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
          <div
            id={`${id}-options`}
            role="listbox"
            aria-label={label}
            aria-multiselectable="true"
            className="max-h-56 overflow-y-auto"
          >
            {filtered.length ? (
              filtered.map((option) => {
                const selected = value.includes(option.value);
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={cn(
                      'flex min-h-9 w-full items-center gap-2 rounded-sm px-2 text-left text-sm outline-none hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:text-accent-foreground',
                    )}
                    onClick={() => toggle(option.value)}
                  >
                    <span className="flex size-4 items-center justify-center rounded border border-primary">
                      {selected && <CheckIcon className="size-3" aria-hidden="true" />}
                    </span>
                    <span className="truncate">{option.label}</span>
                  </button>
                );
              })
            ) : (
              <p className="px-2 py-3 text-sm text-muted-foreground">
                No matching options.
              </p>
            )}
          </div>
          <div className="mt-2 flex justify-between border-t pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={!value.length}
              onClick={() => onChange([])}
            >
              Clear
            </Button>
            <Button type="button" size="sm" onClick={() => setOpen(false)}>
              Done
            </Button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
