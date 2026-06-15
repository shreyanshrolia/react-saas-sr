import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearToken, setToken, type User, type AuthResp, type Role } from "@/src/api/client";

interface Ctx {
  user: User | null;
  loading: boolean;
  login: (phone: string, password: string) => Promise<User>;
  signup: (data: { name: string; phone: string; password: string; role: Role; address?: string }) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<Ctx>({
  user: null,
  loading: true,
  login: async () => { throw new Error("not ready"); },
  signup: async () => { throw new Error("not ready"); },
  logout: async () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const u = await api.get<User>("/auth/me");
      setUser(u);
    } catch {
      setUser(null);
      await clearToken();
    }
  }, []);

  useEffect(() => {
    (async () => {
      await refresh();
      setLoading(false);
    })();
  }, [refresh]);

  const login = useCallback(async (phone: string, password: string) => {
    const res = await api.post<AuthResp>("/auth/login", { phone, password });
    await setToken(res.token);
    setUser(res.user);
    return res.user;
  }, []);

  const signup = useCallback(async (data: { name: string; phone: string; password: string; role: Role; address?: string; security_question?: string; security_answer?: string }) => {
    const res = await api.post<AuthResp>("/auth/signup", data);
    await setToken(res.token);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    await clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
