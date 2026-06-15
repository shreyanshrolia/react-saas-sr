import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Notification } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatDate } from "@/src/utils/format";

const TYPE_ICON: Record<Notification["type"], { icon: any; color: string }> = {
  new_entry: { icon: "shirt", color: colors.primary },
  return_requested: { icon: "help-circle", color: colors.warning },
  return_confirmed: { icon: "checkmark-circle", color: colors.success },
  return_denied: { icon: "close-circle", color: colors.danger },
  delete_requested: { icon: "trash-bin", color: colors.warning },
  delete_confirmed: { icon: "trash", color: colors.danger },
  delete_denied: { icon: "shield-checkmark", color: colors.success },
  client_delete_requested: { icon: "shirt", color: colors.danger },
  client_delete_confirmed: { icon: "person-remove-outline", color: colors.danger },
  client_delete_denied: { icon: "shield-checkmark", color: colors.success },
};

export default function NotificationsScreen() {
  const { user } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.get<Notification[]>("/notifications");
      setItems(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const markRead = async (id: string) => {
    try {
      await api.post(`/notifications/${id}/read`);
      setItems((cur) => cur.map((n) => (n.id === id ? { ...n, read: true } : n)));
    } catch {/* ignore */}
  };

  const markAllRead = async () => {
    try {
      await api.post("/notifications/read-all");
      setItems((cur) => cur.map((n) => ({ ...n, read: true })));
    } catch {/* ignore */}
  };

  const onTap = (n: Notification) => {
    if (!n.read) markRead(n.id);
    // For iron man, navigate to client detail if applicable
    if (user?.role === "iron_man" && n.client_id) {
      router.push(`/(iron)/client/${n.client_id}` as any);
    }
  };

  const unreadCount = items.filter((n) => !n.read).length;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <TouchableOpacity testID="back-button" style={styles.iconBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Notifications</Text>
        {unreadCount > 0 ? (
          <TouchableOpacity testID="mark-all-read-button" onPress={markAllRead}>
            <Text style={styles.markAll}>Mark all read</Text>
          </TouchableOpacity>
        ) : (
          <View style={{ width: 80 }} />
        )}
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : items.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="notifications-outline" size={56} color={colors.textMuted} />
          <Text style={styles.emptyText}>No notifications yet</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(n) => n.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); load(); }}
              tintColor={colors.primary}
            />
          }
          renderItem={({ item }) => {
            const ti = TYPE_ICON[item.type] || { icon: "alert-circle", color: colors.primary };
            const showClientDeleteActions =
              user?.role === "client" && item.type === "client_delete_requested" && item.client_id;
            return (
              <View style={[styles.row, !item.read && styles.rowUnread]} testID={`notif-${item.id}`}>
                <TouchableOpacity
                  style={{ flexDirection: "row", alignItems: "center", gap: spacing.md, flex: 1 }}
                  onPress={() => onTap(item)}
                  activeOpacity={0.85}
                >
                  <View style={[styles.icon, { backgroundColor: ti.color + "20" }]}>
                    <Ionicons name={ti.icon} size={20} color={ti.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.rowTitle, !item.read && { fontWeight: "800" }]}>{item.title}</Text>
                    <Text style={styles.rowMessage} numberOfLines={3}>{item.message}</Text>
                    <Text style={styles.rowDate}>{formatDate(item.created_at)}</Text>
                  </View>
                  {!item.read ? <View style={styles.unreadDot} /> : null}
                </TouchableOpacity>
                {showClientDeleteActions ? (
                  <View style={{ flexDirection: "row", gap: 6, marginTop: 8, flexBasis: "100%" }}>
                    <TouchableOpacity
                      testID={`deny-client-delete-${item.id}`}
                      style={{ flex: 1, paddingVertical: 8, borderRadius: radius.md, backgroundColor: colors.bgSecondary, alignItems: "center" }}
                      onPress={async () => {
                        try {
                          await api.post(`/clients/${item.client_id}/delete-deny`);
                          markRead(item.id);
                        } catch {/* ignore */}
                      }}
                    >
                      <Text style={{ color: colors.text, fontWeight: "700", fontSize: 12 }}>Keep relationship</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      testID={`confirm-client-delete-${item.id}`}
                      style={{ flex: 1, paddingVertical: 8, borderRadius: radius.md, backgroundColor: colors.danger, alignItems: "center" }}
                      onPress={async () => {
                        try {
                          await api.post(`/clients/${item.client_id}/delete-confirm`);
                          markRead(item.id);
                          load();
                        } catch {/* ignore */}
                      }}
                    >
                      <Text style={{ color: colors.textInverse, fontWeight: "700", fontSize: 12 }}>Delete my records</Text>
                    </TouchableOpacity>
                  </View>
                ) : null}
              </View>
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    padding: spacing.lg, borderBottomWidth: 1, borderBottomColor: colors.borderLight, backgroundColor: colors.card,
  },
  iconBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center", borderRadius: radius.md },
  title: { fontSize: 18, fontWeight: "800", color: colors.text },
  markAll: { fontSize: 12, color: colors.primary, fontWeight: "700" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  emptyText: { color: colors.textSecondary },
  row: {
    flexDirection: "row", alignItems: "center", gap: spacing.md, flexWrap: "wrap",
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.sm,
  },
  rowUnread: { borderColor: colors.primary + "33", backgroundColor: "#EEF2FF" + "40" },
  icon: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  rowTitle: { fontSize: 14, fontWeight: "700", color: colors.text },
  rowMessage: { fontSize: 12, color: colors.textSecondary, marginTop: 4 },
  rowDate: { fontSize: 10, color: colors.textMuted, marginTop: 6 },
  unreadDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary },
});
