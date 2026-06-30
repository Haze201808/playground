package main

import (
    "fmt"
    "sort"
)

func main() {
    numbers := []int{5, 2, 9, 1, 5, 6}
    
    // 降順ソート
    sort.Slice(numbers, func(i, j int) bool {
        return numbers[i] > numbers[j]
    })
    
    fmt.Println(numbers) // [9 6 5 5 2 1]
}