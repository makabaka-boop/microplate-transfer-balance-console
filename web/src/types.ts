/** API 契约类型（与 api/app/schemas.py 对应）。 */

export interface FractionDTO {
  numerator: number;
  denominator: number;
}

export interface WellInput {
  id: string;
  volume_ul: number;
  concentration: { numerator: number; denominator: number };
}

export interface TransferInput {
  from: string;
  to: string;
  amount_ul: number;
}

export interface ReviewRequestBody {
  wells: WellInput[];
  transfers: TransferInput[];
}

export interface WellState {
  well: string;
  volume_ul: number;
  concentration: FractionDTO;
  solute_mass: FractionDTO;
}

export interface StepResult {
  step: number;
  from: string;
  to: string;
  amount_ul: number;
  transferred_solute_mass: FractionDTO;
  source_before: WellState;
  source_after: WellState;
  target_before: WellState;
  target_after: WellState;
}

export interface Conservation {
  mass: {
    initial_total_solute_mass: FractionDTO;
    final_total_solute_mass: FractionDTO;
    total_solute_mass_after_each_step: FractionDTO[];
    holds: boolean;
  };
  volume: {
    initial_total_volume_ul: number;
    final_total_volume_ul: number;
    holds: boolean;
  };
}

export interface ReviewOk {
  status: "ok";
  steps: StepResult[];
  final_wells: WellState[];
  conservation: Conservation;
}

export interface ConflictError {
  status: "conflict";
  error: {
    code: "EMPTY_SOURCE" | "INSUFFICIENT_VOLUME";
    step: number;
    from: string;
    to: string;
    requested_ul: number;
    available_ul: number;
    message: string;
  };
}

export interface ValidationIssue {
  loc: string[];
  type: string;
  message: string;
  hint?: string;
}

export interface ValidationError {
  status: "invalid_request";
  errors: ValidationIssue[];
}

export type ReviewResponse = ReviewOk | ConflictError | ValidationError;

/** "3/4"，分母为 1 时只显示分子。 */
export function formatFraction(f: FractionDTO): string {
  return f.denominator === 1 ? `${f.numerator}` : `${f.numerator}/${f.denominator}`;
}

/** 分数小数值（仅用于网格配色，不参与任何结论）。 */
export function fractionValue(f: FractionDTO): number {
  return f.numerator / f.denominator;
}
