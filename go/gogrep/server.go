package main
import (
  "fmt"
  "net/http"
)

func SearchText(w http.ResponseWriter, req *http.Request) {
  kw := req.FormValue("keyword")
  baseDir := req.FormValue("baseDir")
  if kw == "" || baseDir == "" {
    w.WriteHeader(http.StatusBadRequest)
    fmt.Fprintln(w, "Require Argument keyword And baseDir")
  } else {
    se := NewSearchEngine(w)
    se.Run(kw, baseDir)
    }
}

func Server() error {
  http.HandleFunc("/search_text", SearchText)
  return http.ListenAndServe(":8080", nil)
}
