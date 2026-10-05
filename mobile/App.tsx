import { BarlowCondensed_600SemiBold, BarlowCondensed_700Bold } from "@expo-google-fonts/barlow-condensed";
import { Barlow_400Regular, Barlow_500Medium, Barlow_600SemiBold, useFonts } from "@expo-google-fonts/barlow";
import { NavigationContainer, createNavigationContainerRef } from "@react-navigation/native";
import { BottomTabBarProps, createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StatusBar } from "expo-status-bar";
import React, { useEffect } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { AuthProvider, useAuth } from "./src/auth";
import { Banner } from "./src/Banner";
import { useNotifications } from "./src/notifs";
import { onNotificationTap, registerPush } from "./src/push";
import Account from "./src/screens/Account";
import Agreements from "./src/screens/Agreements";
import Alerts from "./src/screens/Alerts";
import Detail from "./src/screens/Detail";
import Login from "./src/screens/Login";
import { C, F } from "./src/theme";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1 } } });
const nav = createNavigationContainerRef<any>();
const Stack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

/** Text-only tab bar: a hi-vis bar above the active tab, count badge on Alerts. */
function TabBar({ state, navigation }: BottomTabBarProps) {
  const { data } = useNotifications();
  const bottom = useSafeAreaInsets().bottom;
  return (
    <View style={[s.bar, { paddingBottom: bottom }]}>
      {state.routes.map((r, i) => {
        const on = state.index === i;
        return (
          <Pressable key={r.key} style={s.tab} onPress={() => !on && navigation.navigate(r.name)}>
            <View style={[s.ind, on && { backgroundColor: C.hivis }]} />
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Text style={[s.tabT, on && { color: "#fff" }]}>{r.name}</Text>
              {r.name === "Alerts" && !!data?.unread && (
                <View style={s.badge}><Text style={s.badgeT}>{data.unread}</Text></View>
              )}
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

function Main() {
  return (
    <Tabs.Navigator tabBar={(p) => <TabBar {...p} />} screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="Agreements" component={Agreements} />
      <Tabs.Screen name="Alerts" component={Alerts} />
      <Tabs.Screen name="Account" component={Account} />
    </Tabs.Navigator>
  );
}

function Root() {
  const { user, ready } = useAuth();

  useEffect(() => {
    if (user) void registerPush();
  }, [user]);

  // Tapping a push/banner opens its agreement.
  useEffect(() => onNotificationTap((id) => nav.isReady() && nav.navigate("Detail", { id })), []);

  if (!ready) return <View style={{ flex: 1, backgroundColor: C.steel }} />;
  return (
    <NavigationContainer ref={nav}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: C.steel },
          headerTintColor: "#fff",
          headerTitleStyle: { fontFamily: F.displayM, fontSize: 20 },
          headerShadowVisible: false,
          headerBackTitle: "Back",
          animation: "slide_from_right",
        }}
      >
        {user ? (
          <>
            <Stack.Screen name="Main" component={Main} options={{ headerShown: false }} />
            <Stack.Screen name="Detail" component={Detail} options={{ title: "" }} />
          </>
        ) : (
          <Stack.Screen name="Login" component={Login} options={{ headerShown: false }} />
        )}
      </Stack.Navigator>
      {user && <Banner onOpen={(id) => nav.navigate("Detail", { id })} />}
    </NavigationContainer>
  );
}

export default function App() {
  const [loaded] = useFonts({ BarlowCondensed_600SemiBold, BarlowCondensed_700Bold, Barlow_400Regular, Barlow_500Medium, Barlow_600SemiBold });
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={qc}>
        <AuthProvider>
          <StatusBar style="light" />
          {loaded ? <Root /> : <View style={{ flex: 1, backgroundColor: C.steel }} />}
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

const s = StyleSheet.create({
  bar: { flexDirection: "row", backgroundColor: C.steel },
  tab: { flex: 1, alignItems: "center", paddingBottom: 14 },
  ind: { height: 3, alignSelf: "stretch", backgroundColor: "transparent", marginBottom: 12 },
  tabT: { fontFamily: F.displayM, fontSize: 18, color: C.onSteel },
  badge: { backgroundColor: C.hivis, borderRadius: 9, minWidth: 18, height: 18, paddingHorizontal: 5, alignItems: "center", justifyContent: "center" },
  badgeT: { color: "#fff", fontFamily: F.bodyB, fontSize: 11 },
});
