# Script which prints out the value of HIMEM (stack location) after computer has booted
# by Quibus based on (https://gist.github.com/FiXato/3093654):

# TCL script for openMSX for easy testing of known machines and extensions.
# (c) 2012 Filip H.F. "FiXato" Slagter
# For inclusion with openMSX, GNU General Public License version 2 (GPLv2, http://www.gnu.org/licenses/gpl-2.0.html) applies. 
# Otherwise you may use this work without restrictions, as long as this notice is included.
# The work is provided "as is" without warranty of any kind, neither express nor implied.

variable machines [openmsx_info machines]

variable index 0

set throttle off

proc do_peek {} {
    variable index
    variable machines
    puts stderr "[utils::get_machine_display_name] - [format "0x%X" [peek16 0xFC4A]] ([expr {$index + 1}]/[llength $machines])"
    incr index
    if {$index < [llength $machines]} {
        do_machine
    } else {
        exit
    }
}

proc do_machine {} {
    variable index
    variable machines
    if { [catch { machine [lindex $machines $index]} errorText] } {
        puts stderr "Skipping $index because of $errorText"
        incr index
        do_machine
    } else {
        catch { set firmwareswitch off }
        after time 10 do_peek
    }
}

do_machine