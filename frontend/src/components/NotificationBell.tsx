import { useCallback, useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { api } from "@/src/api/client";
import { colors, radius } from "@/src/theme/colors";

export default function NotificationBell() {
  const router = useRouter();
  const [count, setCount] = useState(0);

  const load = useCallback(async () => {
    try {
      const { count } = await api.get<{ count: number }>("/notifications/unread-count");
      setCount(count);
    } catch {/* ignore */}
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <TouchableOpacity
      testID="notification-bell"
      style={styles.btn}
      onPress={() => router.push("/notifications")}
      activeOpacity={0.85}
    >
      <Ionicons name="notifications-outline" size={22} color={colors.text} />
      {count > 0 ? (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{count > 99 ? "99+" : count}</Text>
        </View>
      ) : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 40, height: 40, borderRadius: radius.md,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.borderLight,
    alignItems: "center", justifyContent: "center",
  },
  badge: {
    position: "absolute", top: -4, right: -4,
    minWidth: 18, height: 18, borderRadius: 9, paddingHorizontal: 4,
    backgroundColor: colors.danger, alignItems: "center", justifyContent: "center",
    borderWidth: 2, borderColor: colors.bg,
  },
  badgeText: { color: colors.textInverse, fontSize: 10, fontWeight: "800" },
});
