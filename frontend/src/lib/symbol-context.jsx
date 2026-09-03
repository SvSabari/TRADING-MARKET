import React, { createContext, useContext, useState } from 'react';

const SymbolContext = createContext();

export function SymbolProvider({ children }) {
  const [globalSymbol, setGlobalSymbol] = useState("");

  return (
    <SymbolContext.Provider value={{ globalSymbol, setGlobalSymbol }}>
      {children}
    </SymbolContext.Provider>
  );
}

export function useSymbol() {
  return useContext(SymbolContext);
}
