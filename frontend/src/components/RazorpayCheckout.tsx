import { useRef, useState } from "react";
import { ActivityIndicator, Platform, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, spacing } from "@/src/theme/colors";

export interface RazorpayOrderInfo {
  order_id: string;
  amount: number; // paise
  amount_inr: number;
  currency: string;
  key_id: string;
  name: string;
  description: string;
  prefill: { name: string; contact: string; email?: string };
  theme_color: string;
}

export interface RazorpaySuccess {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

interface Props {
  order: RazorpayOrderInfo;
  onSuccess: (s: RazorpaySuccess) => void;
  onClose: () => void;
}

function buildCheckoutHtml(order: RazorpayOrderInfo): string {
  const safe = JSON.stringify(order);
  return `<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
html,body{height:100%;margin:0;background:#FAF9F6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}
.wrap{display:flex;height:100%;align-items:center;justify-content:center;flex-direction:column;gap:14px;padding:24px;text-align:center;color:#0F172A;}
.spin{width:36px;height:36px;border:3px solid #E2E8F0;border-top-color:#1E3A8A;border-radius:50%;animation:s 0.7s linear infinite;}
@keyframes s{to{transform:rotate(360deg);}}
.t{font-size:15px;color:#475569;}
.b{margin-top:20px;padding:10px 18px;background:#1E3A8A;color:#fff;border:0;border-radius:10px;font-weight:700;font-size:14px;}
</style>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
</head>
<body>
<div class="wrap" id="root">
  <div class="spin"></div>
  <div class="t">Opening secure payment…</div>
  <button class="b" onclick="openRzp()" id="retry" style="display:none">Retry payment</button>
</div>
<script>
const ORDER = ${safe};
function send(payload){
  try{
    if(window.ReactNativeWebView){ window.ReactNativeWebView.postMessage(JSON.stringify(payload)); }
  }catch(e){}
}
function openRzp(){
  document.getElementById('retry').style.display='none';
  const options = {
    key: ORDER.key_id,
    amount: ORDER.amount,
    currency: ORDER.currency,
    name: ORDER.name,
    description: ORDER.description,
    order_id: ORDER.order_id,
    prefill: ORDER.prefill,
    theme: { color: ORDER.theme_color },
    handler: function(resp){
      send({type:'success', payload: resp});
    },
    modal: {
      ondismiss: function(){
        document.getElementById('retry').style.display='inline-block';
        send({type:'dismiss'});
      }
    }
  };
  try{
    const rzp = new Razorpay(options);
    rzp.on('payment.failed', function(resp){
      send({type:'failed', payload: resp.error});
    });
    rzp.open();
  }catch(e){
    send({type:'error', payload: String(e && e.message || e)});
  }
}
// wait a tick so the spinner renders, then open
setTimeout(openRzp, 200);
</script>
</body>
</html>`;
}

export default function RazorpayCheckout({ order, onSuccess, onClose }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const webRef = useRef<WebView>(null);

  const html = buildCheckoutHtml(order);

  const handleMessage = (e: WebViewMessageEvent) => {
    try {
      const msg = JSON.parse(e.nativeEvent.data) as
        | { type: "success"; payload: RazorpaySuccess }
        | { type: "dismiss" }
        | { type: "failed"; payload: { description?: string; reason?: string } }
        | { type: "error"; payload: string };
      if (msg.type === "success") {
        onSuccess(msg.payload);
        return;
      }
      if (msg.type === "failed") {
        setError(msg.payload?.description || msg.payload?.reason || "Payment failed");
        return;
      }
      if (msg.type === "error") {
        setError(msg.payload);
        return;
      }
      // dismiss: just show retry inside the webview, user can close
    } catch {
      // ignore malformed
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <TouchableOpacity
          testID="rzp-close-button"
          style={styles.closeBtn}
          onPress={() => { setClosing(true); onClose(); }}
        >
          <Ionicons name="close" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Secure Payment</Text>
        <View style={{ width: 40 }} />
      </View>

      {closing ? (
        <View style={styles.loading}><ActivityIndicator color={colors.primary} /></View>
      ) : (
        <View style={{ flex: 1, backgroundColor: colors.bg }}>
          <WebView
            ref={webRef}
            originWhitelist={["*"]}
            source={{ html, baseUrl: "https://grihkari.app" }}
            onMessage={handleMessage}
            javaScriptEnabled
            domStorageEnabled
            mixedContentMode="always"
            style={{ flex: 1, backgroundColor: colors.bg }}
            startInLoadingState
            renderLoading={() => (
              <View style={styles.loading}>
                <ActivityIndicator color={colors.primary} />
                <Text style={styles.loadingText}>Loading Razorpay…</Text>
              </View>
            )}
            onShouldStartLoadWithRequest={(req) => {
              // Allow razorpay + about:blank only
              return (
                req.url.startsWith("https://checkout.razorpay.com") ||
                req.url.startsWith("https://api.razorpay.com") ||
                req.url.startsWith("https://grihkari.app") ||
                req.url.startsWith("about:") ||
                req.url.startsWith("data:") ||
                req.url === "" ||
                Platform.OS === "web"
              );
            }}
          />
          {error ? (
            <View style={styles.errorBanner}>
              <Ionicons name="alert-circle" size={16} color={colors.danger} />
              <Text style={styles.errorText} numberOfLines={2}>{error}</Text>
            </View>
          ) : null}
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.card },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.lg, paddingVertical: spacing.md,
    borderBottomWidth: 1, borderBottomColor: colors.borderLight, backgroundColor: colors.card,
  },
  closeBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center", borderRadius: radius.md },
  title: { fontSize: 16, fontWeight: "800", color: colors.text },
  loading: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    alignItems: "center", justifyContent: "center", backgroundColor: colors.bg, gap: 8,
  },
  loadingText: { color: colors.textSecondary, fontSize: 13 },
  errorBanner: {
    position: "absolute", bottom: spacing.lg, left: spacing.lg, right: spacing.lg,
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.dangerLight, padding: spacing.md, borderRadius: radius.md,
  },
  errorText: { flex: 1, color: colors.danger, fontSize: 13, fontWeight: "600" },
});
