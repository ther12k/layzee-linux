/* lekuvo sciter host — minimal C host on the vendored 4.4.8 GTK runtime.
 *
 * Responsibilities:
 *  - frameless alpha window, always-on-top, skip taskbar, top of screen
 *  - click-through: applies a GTK input region from the page's hostTick()
 *  - drag: when the page reports drag=1, moves the window with the
 *    global (screen) pointer so drags cross the GNOME top bar freely
 */
#include <gtk/gtk.h>
#include <uchar.h> /* char16_t for the SDK's WCHAR in C mode */
#include <string.h>
#include <stdlib.h>
#include "sciter-x-api.h"

/* The engine exports only SciterAPI(); everything else comes through
 * the ISciterAPI vtable it returns. */
extern ISciterAPI *SciterAPI(void); /* resolved by -lsciter-gtk */
static ISciterAPI *API = NULL;

#define WIN_H 300

static HWINDOW g_hwnd = 0;
static GtkWindow *g_win = NULL;
static int g_dragging = 0;
static int g_quit = 0;
static int g_drag_base_sx = 0, g_drag_base_sy = 0;
static int g_drag_base_wx = 0, g_drag_base_wy = 0;

static void apply_input_region(int x, int y, int w, int h) {
    if (!g_win) return;
    cairo_rectangle_int_t rect = { x, y, w, h };
    cairo_region_t *reg = cairo_region_create_rectangle(&rect);
    gtk_widget_input_shape_combine_region(GTK_WIDGET(g_win), reg);
    cairo_region_destroy(reg);
}

static int json_int_field(const char *buf, const char *key, int fallback) {
    /* kept for future JSON-style payloads; comma protocol doesn't use it */
    (void)buf; (void)key;
    return fallback;
}

/* page protocol: hostTick() -> "rx,ry,rw,rh,drag" (logical px, string) */
static gboolean on_tick(gpointer user_data) {
    (void)user_data;
    if (!g_hwnd) return TRUE;

    VALUE rv;
    if (API->SciterCall(g_hwnd, "hostTick", 0, NULL, &rv)) {
        API->ValueToString(&rv, CVT_SIMPLE);
        const WCHAR *ws = (const WCHAR *)(uintptr_t)rv.d; /* string ptr in payload slot */
        if (ws) {
            char buf[128] = {0};
            for (UINT i = 0; ws[i] && i < 127; ++i) buf[i] = (char)(ws[i] & 0xff);
            int rx = 0, ry = 0, rw = 300, rh = 40, drag = 0, quit = 0;
            if (sscanf(buf, "%d,%d,%d,%d,%d,%d", &rx, &ry, &rw, &rh, &drag, &quit) >= 4) {
                apply_input_region(rx, ry, rw, rh);
                if (drag && !g_dragging) {
                    g_dragging = 1;
                    GdkDisplay *d = gtk_widget_get_display(GTK_WIDGET(g_win));
                    GdkScreen *s = gtk_widget_get_screen(GTK_WIDGET(g_win));
                    int px = 0, py = 0;
                    gdk_display_get_pointer(d, &s, &px, &py, NULL);
                    gint wx = 0, wy = 0;
                    gtk_window_get_position(g_win, &wx, &wy);
                    g_drag_base_sx = px; g_drag_base_sy = py;
                    g_drag_base_wx = wx; g_drag_base_wy = wy;
                } else if (!drag) {
                    g_dragging = 0;
                }
                if (quit) g_quit = 1;
            }
        }
        API->ValueClear(&rv);
    }

    if (g_dragging) {
        GdkDisplay *d = gtk_widget_get_display(GTK_WIDGET(g_win));
        GdkScreen *s = gtk_widget_get_screen(GTK_WIDGET(g_win));
        int px = 0, py = 0;
        gdk_display_get_pointer(d, &s, &px, &py, NULL);
        gtk_window_move(g_win,
                        g_drag_base_wx + (px - g_drag_base_sx),
                        g_drag_base_wy + (py - g_drag_base_sy));
    }
    if (g_quit) {
        gtk_main_quit();
        return FALSE;
    }
    return TRUE;
}

int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    API = SciterAPI();
    if (!API) return 1;

    const char *html = (argc > 1) ? argv[1]
        : "sciter_frontend/notch.html";
    char url[1024];
    if (html[0] == '/') snprintf(url, sizeof(url), "file://%s", html);
    else { char cwd[512]; getcwd(cwd, sizeof(cwd)); snprintf(url, sizeof(url), "file://%s/%s", cwd, html); }

    g_hwnd = API->SciterCreateWindow(SW_POPUP | SW_ALPHA, NULL, NULL, NULL, NULL);
    if (!g_hwnd) return 1;

    /* HWINDOW on GTK is the inner GtkDrawingArea — the toplevel is the window */
    g_win = GTK_WINDOW(gtk_widget_get_toplevel(GTK_WIDGET(g_hwnd)));
    gtk_window_set_keep_above(g_win, TRUE);
    gtk_window_set_skip_taskbar_hint(g_win, TRUE);
    gtk_window_set_skip_pager_hint(g_win, TRUE);

    GdkScreen *screen = gtk_window_get_screen(g_win);
    int sw = gdk_screen_get_width(screen);
    int win_w = sw; /* full screen width, logical px */
    gtk_window_set_default_size(g_win, win_w, WIN_H);
    gtk_window_move(g_win, 0, 0);
    apply_input_region((sw - 320) / 2, 0, 320, 42);

    wchar_t wurl[1024];
    for (size_t i = 0; i < strlen(url) && i < 1023; ++i) wurl[i] = url[i];
    wurl[strlen(url) < 1023 ? strlen(url) : 1023] = 0;
    API->SciterLoadFile(g_hwnd, wurl);
    gtk_widget_show_all(GTK_WIDGET(g_win));

    g_timeout_add(60, on_tick, NULL);
    gtk_main();
    return 0;
}
