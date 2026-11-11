#include <gtk/gtk.h>
#include <iostream>
#include <string>
#include "sciter-x.h"
#include "sciter-x-window.hpp"

class NotchApp : public sciter::window {
public:
    NotchApp() : window(SW_POPUP | SW_ALPHA | SW_OWNS_VM) {}

    // Expose native functions to QuickJS
    SOM_PASSPORT_BEGIN(NotchApp)
        SOM_FUNCS(
            SOM_FUNC(on_action),
            SOM_FUNC(set_region)
        )
    SOM_PASSPORT_END

    sciter::value on_action(sciter::string action) {
        aux::w2a a(action.c_str());
        std::cout << "ACTION:" << a.c_str() << std::endl;
        return sciter::value(true);
    }

    sciter::value set_region(int x, int y, int w, int h) {
        GtkWindow* win = sciter::gwindow(get_hwnd());
        if (win) {
            cairo_rectangle_int_t rect = { x, y, w, h };
            cairo_region_t* reg = cairo_region_create_rectangle(&rect);
            gtk_widget_input_shape_combine_region(GTK_WIDGET(win), reg);
            cairo_region_destroy(reg);
        }
        return sciter::value(true);
    }
};

#include "sciter-gtk-main.cpp"

int uimain(std::function<int()> run) {
    sciter::om::hcontrol<NotchApp> wnd = new NotchApp();

    GtkWindow* win = sciter::gwindow(wnd->get_hwnd());
    if (win) {
        gtk_window_set_keep_above(win, TRUE);
        gtk_window_set_skip_taskbar_hint(win, TRUE);
        gtk_window_set_skip_pager_hint(win, TRUE);
        
        GdkScreen* screen = gtk_widget_get_screen(GTK_WIDGET(win));
        int screen_w = gdk_screen_get_width(screen);
        gtk_window_set_default_size(win, screen_w, 220);
        gtk_window_move(win, 0, 0);

        // Initial shape
        int init_w = 320;
        int init_h = 42;
        int init_x = (screen_w - init_w) / 2;
        cairo_rectangle_int_t rect = { init_x, 0, init_w, init_h };
        cairo_region_t* reg = cairo_region_create_rectangle(&rect);
        gtk_widget_input_shape_combine_region(GTK_WIDGET(win), reg);
        cairo_region_destroy(reg);
    }

    wnd->load(WSTR("file:///home/rizky/Workspace/Learning/notchbar/sciter_frontend/notch.html"));
    wnd->expand();

    return run();
}
