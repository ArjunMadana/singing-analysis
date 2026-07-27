export type ImportDraft<TInspection = unknown> = {
  projectId: string | null;
  inspection: TInspection | null;
  roles: Record<number, string>;
};

export function createImportDraft<TInspection = unknown>(
  projectId?: string | null,
): ImportDraft<TInspection>;

export function createInspectedImportDraft<
  TInspection extends {
    streams: Array<{ index: number; suggested_role: string }>;
  },
>(projectId: string, inspection: TInspection): ImportDraft<TInspection>;

export function importDraftForProject<TInspection>(
  draft: ImportDraft<TInspection>,
  projectId: string,
): ImportDraft<TInspection>;
