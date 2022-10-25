package main
import (
  "bufio"
  "net/http"
  _"embed"
  "fmt"
  "os"
  "strings"
)

func main() {
  args := os.Args[1: ]
  switch len(args) {
    case 0:
      actionZero()
    case 1:
      actionOne(args)
    case 2:
      actionTwo(args)
    case 3:
      actionThree(args)
    default:
      actionError()
  }
}

//go:embed help.txt
var help string
func actionZero() {
  fmt.Print(help)
}

func actionOne(args []string) {
  if "server" == strings.ToLower(args[0]){
    fmt.Println("Ctrl+C Quit")
    Server()
  } else {
    fmt.Fprintf(os.Stderr, "Input Error: Invalid Option\n%s", help)
  }
}

func actionTwo(args []string) {
  se := NewSearchEngine(os.Stdout)
  se.Run(args[0], args[1])
}

func actionThree(args []string) {
  host := strings.TrimSpace(args[0])
  kw := strings.TrimSpace(args[1])
  dir := strings.TrimSpace(args[2])
  url := fmt.Sprintf("http://%s:8080/search_text?keyword=%s&baseDir=%s", host, kw, dir)
  res, err := http.Get(url)
  if err != nil {
    fmt.Fprintln(os.Stderr, err)
    }
  defer res.Body.Close()
  s := bufio.NewScanner(res.Body)
  for s.Scan() {
    fmt.Println(s.Text())
  }
}

func actionError() {
  fmt.Fprintf(os.Stderr, "Input Error: Argument Too Much\n%s", help)
}
