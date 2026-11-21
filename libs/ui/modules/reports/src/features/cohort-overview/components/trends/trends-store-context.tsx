'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import { createStore, useStore, type StoreApi } from 'zustand';

export interface TrendsStoreState {
  /** Explicitly selected publication IDs, or null to default to compatible PO-set snapshots. */
  customTrendPubIds: string[] | null;
  /** Currently plotted PO code in the trend area chart. */
  selectedTrendPoCode: string;
  togglePublication: (pubId: string, compatibleIds: string[]) => void;
  resetPublications: () => void;
  setSelectedPoCode: (code: string) => void;
}

export function createTrendsStore(): StoreApi<TrendsStoreState> {
  return createStore<TrendsStoreState>((set) => ({
    customTrendPubIds: null,
    selectedTrendPoCode: '',
    togglePublication: (pubId, compatibleIds) =>
      set((state) => {
        const current =
          state.customTrendPubIds !== null
            ? state.customTrendPubIds
            : compatibleIds;
        const next = current.includes(pubId)
          ? current.filter((id) => id !== pubId)
          : [...current, pubId];
        return { customTrendPubIds: next };
      }),
    resetPublications: () => set({ customTrendPubIds: null }),
    setSelectedPoCode: (code) => set({ selectedTrendPoCode: code }),
  }));
}

const TrendsStoreContext = createContext<StoreApi<TrendsStoreState> | null>(
  null,
);

/**
 * Zustand + React Context Provider: creates an isolated per-mount vanilla
 * Zustand store so SSR/multiple instances never share singleton state, while
 * enabling fine-grained selector subscriptions across child panels.
 */
export function TrendsStoreProvider({ children }: { children: ReactNode }) {
  const [store] = useState(createTrendsStore);
  return (
    <TrendsStoreContext.Provider value={store}>
      {children}
    </TrendsStoreContext.Provider>
  );
}

export function useTrendsStore<T>(selector: (state: TrendsStoreState) => T): T {
  const store = useContext(TrendsStoreContext);
  if (!store) {
    throw new Error('useTrendsStore must be used inside <TrendsStoreProvider>.');
  }
  return useStore(store, selector);
}
