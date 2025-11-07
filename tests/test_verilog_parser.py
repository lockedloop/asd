"""Unit tests for Verilog parser."""

import pytest

from asd.utils.verilog_parser import VerilogParser


def test_parse_simple_module(tmp_path):
    """Test parsing a simple Verilog module."""
    parser = VerilogParser()

    # Create test Verilog file
    verilog_code = """
    module test_module #(
        parameter WIDTH = 8,
        parameter DEPTH = 16
    )(
        input  logic             clk,
        input  logic             rst,
        input  logic [WIDTH-1:0] data_in,
        output logic [WIDTH-1:0] data_out
    );
        // Module body
    endmodule
    """

    test_file = tmp_path / "test.sv"
    test_file.write_text(verilog_code)

    # Parse module
    module = parser.parse_file(test_file)

    assert module.name == "test_module"
    assert len(module.parameters) == 2
    assert len(module.ports) == 4

    # Check parameters
    param_names = [p.name for p in module.parameters]
    assert "WIDTH" in param_names
    assert "DEPTH" in param_names

    # Check ports
    port_names = [p.name for p in module.ports]
    assert "clk" in port_names
    assert "rst" in port_names
    assert "data_in" in port_names
    assert "data_out" in port_names


def test_parse_with_imports(tmp_path):
    """Test parsing module with package imports."""
    parser = VerilogParser()

    verilog_code = """
    import pkg_a::*;
    import pkg_b::*;

    module test_module (
        input logic clk,
        output logic out
    );
    endmodule
    """

    test_file = tmp_path / "test.sv"
    test_file.write_text(verilog_code)

    module = parser.parse_file(test_file)

    assert "pkg_a" in module.packages
    assert "pkg_b" in module.packages


def test_parse_with_instances(tmp_path):
    """Test parsing module with instantiations."""
    parser = VerilogParser()

    verilog_code = """
    module top_module (
        input logic clk
    );

        SubModule u_sub1 (.clk(clk));

        AnotherModule #(
            .PARAM(10)
        ) u_another (
            .clk(clk)
        );

    endmodule
    """

    test_file = tmp_path / "test.sv"
    test_file.write_text(verilog_code)

    module = parser.parse_file(test_file)

    assert "SubModule" in module.instances
    assert "AnotherModule" in module.instances


def test_parse_default_values():
    """Test parsing Verilog default values."""
    parser = VerilogParser()

    # Binary
    assert parser.parse_default_value("8'b10101010") == 0xAA
    assert parser.parse_default_value("1'b1") == 1

    # Hexadecimal
    assert parser.parse_default_value("16'hDEAD") == 0xDEAD
    assert parser.parse_default_value("8'h42") == 0x42

    # Decimal
    assert parser.parse_default_value("100") == 100
    assert parser.parse_default_value("8'd255") == 255

    # String
    assert parser.parse_default_value('"hello"') == "hello"


def test_remove_comments():
    """Test comment removal."""
    parser = VerilogParser()

    code_with_comments = """
    // This is a single-line comment
    module test /* inline comment */ (
        input clk // another comment
    );
    /* Multi-line
       comment
       block */
    endmodule
    """

    cleaned = parser._remove_comments(code_with_comments)

    assert "This is a single-line comment" not in cleaned
    assert "inline comment" not in cleaned
    assert "another comment" not in cleaned
    assert "Multi-line" not in cleaned


def test_no_module_error(tmp_path):
    """Test error when no module found."""
    parser = VerilogParser()

    verilog_code = """
    // Just a comment, no module
    `define SOMETHING 1
    """

    test_file = tmp_path / "test.sv"
    test_file.write_text(verilog_code)

    with pytest.raises(ValueError, match="No module found"):
        parser.parse_file(test_file)
