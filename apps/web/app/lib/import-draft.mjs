export function createImportDraft(projectId = null) {
  return {
    projectId,
    inspection: null,
    roles: {},
  };
}

export function createInspectedImportDraft(projectId, inspection) {
  return {
    projectId,
    inspection,
    roles: Object.fromEntries(
      inspection.streams.map((stream) => [stream.index, stream.suggested_role]),
    ),
  };
}

export function importDraftForProject(draft, projectId) {
  return draft?.projectId === projectId ? draft : createImportDraft(projectId);
}
