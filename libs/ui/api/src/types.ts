/** Wire values stay strings: never round decimals or reinterpret UTC timestamps. */
export type UUID = string;
export type UTCDateTime = string;
export type Decimal = string;
export type Score = Decimal | null;
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export type ValidationErrors = Record<string, string | string[]>;
export type ApiErrorKind =
  | 'unauthorized'
  | 'forbidden'
  | 'validation'
  | 'conflict'
  | 'unavailable'
  | 'unexpected';
