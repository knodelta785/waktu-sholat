#!/usr/bin/env python3
"""Menambahkan bagian native ke proyek Android hasil `npx cap add android`:
widget 4x1, jembatan widget, izin, audio azan, versi, dan penandatanganan."""
import os, re, shutil, sys, json

ROOT = os.getcwd()
APP_ID = "id.ongarand.waktusholat"
AND = os.path.join(ROOT, "android")
MAIN = os.path.join(AND, "app", "src", "main")
RES = os.path.join(MAIN, "res")
JAVA = os.path.join(MAIN, "java", *APP_ID.split("."))
BUILD_NUM = os.environ.get("BUILD_NUM", "1")


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------- Java ----------
w(os.path.join(JAVA, "MainActivity.java"), f"""package {APP_ID};

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{
    @Override
    public void onCreate(Bundle savedInstanceState) {{
        registerPlugin(WidgetPlugin.class);
        super.onCreate(savedInstanceState);
    }}
}}
""")

w(os.path.join(JAVA, "WidgetPlugin.java"), f"""package {APP_ID};

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "WidgetBridge")
public class WidgetPlugin extends Plugin {{
    @PluginMethod
    public void update(PluginCall call) {{
        String json = call.getString("json", "");
        getContext().getSharedPreferences("ws_widget", 0).edit().putString("json", json).apply();
        WsWidget.refresh(getContext());
        call.resolve();
    }}
}}
""")

w(os.path.join(JAVA, "WsWidget.java"), f"""package {APP_ID};

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.widget.RemoteViews;
import org.json.JSONObject;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Locale;
import java.util.TimeZone;

public class WsWidget extends AppWidgetProvider {{
    static final String[] KEYS = {{"subuh", "dzuhur", "ashar", "maghrib", "isya"}};
    static final String[] NAMES = {{"Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"}};
    static final int[] CELL = {{R.id.ws_c0, R.id.ws_c1, R.id.ws_c2, R.id.ws_c3, R.id.ws_c4}};
    static final int[] NAME = {{R.id.ws_n0, R.id.ws_n1, R.id.ws_n2, R.id.ws_n3, R.id.ws_n4}};
    static final int[] TIME = {{R.id.ws_t0, R.id.ws_t1, R.id.ws_t2, R.id.ws_t3, R.id.ws_t4}};

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {{
        refresh(context);
    }}

    public static void refresh(Context c) {{
        try {{
            AppWidgetManager m = AppWidgetManager.getInstance(c);
            int[] ids = m.getAppWidgetIds(new ComponentName(c, WsWidget.class));
            if (ids == null || ids.length == 0) return;
            RemoteViews rv = new RemoteViews(c.getPackageName(), R.layout.ws_widget);
            long wait = fill(c, rv);
            Intent launch = c.getPackageManager().getLaunchIntentForPackage(c.getPackageName());
            if (launch != null) {{
                PendingIntent open = PendingIntent.getActivity(c, 0, launch, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
                rv.setOnClickPendingIntent(R.id.ws_root, open);
            }}
            m.updateAppWidget(ids, rv);
            Intent up = new Intent(c, WsWidget.class);
            up.setAction(AppWidgetManager.ACTION_APPWIDGET_UPDATE);
            up.putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids);
            PendingIntent pi = PendingIntent.getBroadcast(c, 7, up, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
            if (am != null) am.setAndAllowWhileIdle(AlarmManager.RTC, System.currentTimeMillis() + wait, pi);
        }} catch (Exception e) {{
            // widget tidak boleh membuat aplikasi berhenti
        }}
    }}

    static int toMin(String hm) {{
        try {{
            String[] p = hm.split(":");
            return Integer.parseInt(p[0].trim()) * 60 + Integer.parseInt(p[1].trim());
        }} catch (Exception e) {{
            return -1;
        }}
    }}

    /** Mengisi tampilan. Mengembalikan jeda (ms) sampai pembaruan berikutnya. */
    static long fill(Context c, RemoteViews rv) {{
        String raw = c.getSharedPreferences("ws_widget", 0).getString("json", "");
        if (raw == null || raw.length() < 5) raw = c.getSharedPreferences("CapacitorStorage", 0).getString("ws_widget_json", "");
        JSONObject day = null;
        int nowMin = 0, sec = 0;
        try {{
            JSONObject root = new JSONObject(raw);
            int tz = root.optInt("tz", 7);
            TimeZone zone = TimeZone.getTimeZone("GMT" + (tz >= 0 ? "+" : "-") + Math.abs(tz));
            Calendar now = Calendar.getInstance(zone);
            nowMin = now.get(Calendar.HOUR_OF_DAY) * 60 + now.get(Calendar.MINUTE);
            sec = now.get(Calendar.SECOND);
            SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
            f.setTimeZone(zone);
            JSONObject days = root.optJSONObject("days");
            if (days != null) day = days.optJSONObject(f.format(now.getTime()));
        }} catch (Exception e) {{
            day = null;
        }}
        int next = -1;
        int nextMin = -1;
        for (int i = 0; i < 5; i++) {{
            String hm = day == null ? "--:--" : day.optString(KEYS[i], "--:--");
            int mn = toMin(hm);
            if (next < 0 && mn > nowMin) {{ next = i; nextMin = mn; }}
            rv.setTextViewText(NAME[i], NAMES[i]);
            rv.setTextViewText(TIME[i], hm);
        }}
        boolean tomorrow = day != null && next < 0;
        int hi = next >= 0 ? next : (tomorrow ? 0 : -1);
        for (int i = 0; i < 5; i++) {{
            boolean on = i == hi;
            rv.setInt(CELL[i], "setBackgroundResource", on ? R.drawable.ws_cell_next : R.drawable.ws_cell_none);
            rv.setTextColor(NAME[i], on ? Color.parseColor("#124434") : Color.parseColor("#C9DDD2"));
            rv.setTextColor(TIME[i], on ? Color.parseColor("#124434") : Color.WHITE);
        }}
        long waitMin;
        if (next >= 0) waitMin = nextMin + 1 - nowMin;
        else if (day == null) waitMin = 5;
        else waitMin = 24 * 60 + 5 - nowMin;
        if (waitMin < 1) waitMin = 1;
        long ms = (waitMin * 60L - sec) * 1000L;
        return ms < 15000L ? 15000L : ms;
    }}
}}
""")

# ---------- Sumber daya widget ----------
cells = ""
for i in range(5):
    cells += f"""    <LinearLayout
        android:id="@+id/ws_c{i}"
        android:layout_width="0dp"
        android:layout_height="match_parent"
        android:layout_weight="1"
        android:layout_margin="2dp"
        android:gravity="center"
        android:orientation="vertical">
        <TextView
            android:id="@+id/ws_n{i}"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:maxLines="1"
            android:textSize="11sp" />
        <TextView
            android:id="@+id/ws_t{i}"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:maxLines="1"
            android:textSize="16sp"
            android:textStyle="bold" />
    </LinearLayout>
"""
w(os.path.join(RES, "layout", "ws_widget.xml"), f"""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/ws_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/ws_widget_bg"
    android:gravity="center"
    android:orientation="horizontal"
    android:padding="4dp">
{cells}</LinearLayout>
""")
w(os.path.join(RES, "drawable", "ws_widget_bg.xml"), """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#164A39" />
    <corners android:radius="20dp" />
</shape>
""")
w(os.path.join(RES, "drawable", "ws_cell_next.xml"), """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#F4EFE0" />
    <corners android:radius="14dp" />
</shape>
""")
w(os.path.join(RES, "drawable", "ws_cell_none.xml"), """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#00000000" />
    <corners android:radius="14dp" />
</shape>
""")
w(os.path.join(RES, "xml", "ws_widget_info.xml"), """<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/ws_widget_desc"
    android:initialLayout="@layout/ws_widget"
    android:minHeight="40dp"
    android:minWidth="250dp"
    android:resizeMode="horizontal"
    android:targetCellHeight="1"
    android:targetCellWidth="4"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
""")
w(os.path.join(RES, "values", "ws_strings.xml"), """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="ws_widget_desc">Jadwal sholat hari ini</string>
</resources>
""")

w(os.path.join(RES, "drawable", "ic_stat_ws.xml"), """<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M12,22c1.1,0 2,-0.9 2,-2h-4c0,1.1 0.9,2 2,2zM18,16v-5c0,-3.07 -1.63,-5.64 -4.5,-6.32V4c0,-0.83 -0.67,-1.5 -1.5,-1.5s-1.5,0.67 -1.5,1.5v0.68C7.64,5.36 6,7.92 6,11v5l-2,2v1h16v-1l-2,-2z" />
</vector>
""")

# ---------- AndroidManifest ----------
mf = os.path.join(MAIN, "AndroidManifest.xml")
m = open(mf, encoding="utf-8").read()
if "WsWidget" not in m:
    receiver = """
        <receiver android:name=".WsWidget" android:exported="false">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data android:name="android.appwidget.provider" android:resource="@xml/ws_widget_info" />
        </receiver>
    </application>"""
    m = m.replace("</application>", receiver, 1)
    perms = """
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.USE_EXACT_ALARM" />
    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
</manifest>"""
    m = m.replace("</manifest>", perms, 1)
    open(mf, "w", encoding="utf-8").write(m)

# ---------- Audio azan (opsional, disediakan pemilik) ----------
azan_src = os.path.join(ROOT, "azan")
azan_list = []
names = []
nf = os.path.join(azan_src, "nama.txt")
if os.path.exists(nf):
    names = [l.strip() for l in open(nf, encoding="utf-8").read().splitlines() if l.strip()]
for i in (1, 2):
    f = os.path.join(azan_src, f"azan{i}.mp3")
    if os.path.exists(f):
        os.makedirs(os.path.join(RES, "raw"), exist_ok=True)
        os.makedirs(os.path.join(ROOT, "www", "audio"), exist_ok=True)
        shutil.copy(f, os.path.join(RES, "raw", f"azan{i}.mp3"))
        shutil.copy(f, os.path.join(ROOT, "www", "audio", f"azan{i}.mp3"))
        azan_list.append({"id": f"azan{i}", "name": names[i - 1] if len(names) >= i else f"Azan {i}"})
w(os.path.join(ROOT, "www", "azan.json"), json.dumps(azan_list, ensure_ascii=False))
print("Azan terpasang:", [a["id"] for a in azan_list] or "tidak ada (taruh azan/azan1.mp3 dan azan/azan2.mp3)")

# ---------- Versi dan penandatanganan ----------
bg = os.path.join(AND, "app", "build.gradle")
g = open(bg, encoding="utf-8").read()
g = re.sub(r"versionCode\s+\d+", f"versionCode {BUILD_NUM}", g, count=1)
g = re.sub(r'versionName\s+"[^"]*"', f'versionName "1.2.{BUILD_NUM}"', g, count=1)
ks = os.environ.get("KS_FILE", "")
if ks and os.path.exists(ks) and "wsrelease" not in g:
    g += f"""

android {{
    signingConfigs {{
        wsrelease {{
            storeFile file("{ks}")
            storePassword System.getenv("KS_PASS")
            keyAlias "waktu"
            keyPassword System.getenv("KS_PASS")
        }}
    }}
    buildTypes {{
        release {{
            signingConfig signingConfigs.wsrelease
        }}
    }}
}}
"""
    print("Penandatanganan rilis diaktifkan")
open(bg, "w", encoding="utf-8").write(g)
print("Patch Android selesai, build", BUILD_NUM)
