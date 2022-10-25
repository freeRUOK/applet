package main
import (
  "bufio"
  "io"
  "io/ioutil"
  "fmt"
  "path"
  "strings"
  "sort"
  "os"
)

type SearchEngine struct {
  keyword string; 
  ignoreCase bool; 
  extends []string; 
  writer io.Writer
}

func NewSearchEngine(writer io.Writer) SearchEngine {
  extends := []string{".txt{", ".go", ".py", ".md", ".js", ".c", ".cs", ".cpp", ".java", ".rs", ".xml", ".json", ".html", ".htm", ".lua"}
  sort.Strings(extends)
  return SearchEngine{ignoreCase: false, 
    extends: extends, 
    writer: writer}
}

func (se *SearchEngine) Run(kw string, basePath string) error {
  if se.ignoreCase{
    se.keyword = strings.ToLower(strings.TrimSpace(kw))
  } else {
    se.keyword = strings.TrimSpace(kw)
  }
  if err := se.findFile(basePath); err != nil {
    return err
  }
  return nil
}

func (se *SearchEngine) findFile(dir string) error {
  files, err := ioutil.ReadDir(dir)
  if err != nil {
    return err
  }
  for _, file := range files {
    if file.IsDir() {
      se.findFile(path.Join(dir, file.Name()))
    } else {
      extName := path.Ext(file.Name())
      i := sort.SearchStrings(se.extends, extName)
      if i < len(se.extends) && extName == se.extends[i]{
        se.searchText(path.Join(dir, file.Name()))
      }
    }
  }
  return nil
}

func (se *SearchEngine) searchText(filename string) error {
  file, err := os.Open(filename)
  if err != nil {
    return err
  }
  defer file.Close()
  filename = fmt.Sprintf("%s\n", filename)
  scanner := bufio.NewScanner(file)
  lineNum := 1
  for scanner.Scan() {
    text := scanner.Text()
    src := text
    if se.ignoreCase {
      text = strings.ToLower(text)
    }
    if strings.Contains(text, se.keyword) {
      fmt.Fprintf(se.writer, "%s%d.%s\n", filename, lineNum, src)
      filename = ""
    }
    lineNum += 1
  }
  return nil
}
